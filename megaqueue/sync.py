"""Download engine ↔ DB sync: match status entries to records, expand folders, update per-file state."""

import logging
from datetime import datetime

from megaqueue import config, lifecycle, metadata
from megaqueue.enums import DownloadStatus, FileStatus
from megaqueue.mega_urls import normalize, extract_folder_id, is_folder_url
from megaqueue.models import db_session, Download, DownloadFile
from megaqueue.notifications import notify_failure, notify_needs_review

log = logging.getLogger(__name__)


def match_download_files(mega_downloads, download_files):
    """Match download engine entries to DownloadFile records.

    Uses three-tier matching:
    1. Direct URL match (for single file downloads)
    2. sourceUrl match (for folder-split entries)
    3. Folder-ID match: extract ###n={folderId} from per-file URL, match against
       DownloadFile records whose URL is a recognised folder URL with the same
       folder ID (new or old format).

    Returns dict: DownloadFile.id -> list[download entry].
    A single DownloadFile may match multiple entries (folder splits).
    """
    file_by_norm = {}
    file_by_url = {}
    file_by_folder_id = {}
    for df in download_files:
        file_by_norm[normalize(df.url)] = df
        file_by_url[df.url] = df
        folder_id = extract_folder_id(df.url)
        if folder_id and is_folder_url(df.url):
            file_by_folder_id[folder_id] = df

    matched = {}

    for dl_entry in mega_downloads:
        norm = normalize(dl_entry.get("url", ""))
        df = file_by_norm.get(norm)

        if df is None:
            source_url = dl_entry.get("sourceUrl", "")
            if source_url:
                df = file_by_url.get(source_url)
                if df is None:
                    df = file_by_norm.get(normalize(source_url))

        if df is None:
            folder_id = extract_folder_id(dl_entry.get("url", ""))
            if folder_id:
                df = file_by_folder_id.get(folder_id)

        if df is not None:
            matched.setdefault(df.id, []).append(dl_entry)

    return matched


def maybe_expand_folder_files(download, initial_matches):
    """Expand folder-URL DownloadFiles into per-file child records.

    When a folder URL DownloadFile matches multiple download entries (folder split)
    and has no existing children, creates one child DownloadFile per entry.
    The children track individual file progress; the parent becomes a container.

    Idempotent: skips files that already have children.
    """
    for df in list(download.top_level_files):
        if df.children:
            continue
        entries = initial_matches.get(df.id, [])
        entries = [e for e in entries if e.get("status") != "Pending"]
        if not entries:
            continue
        if not is_folder_url(df.url):
            continue

        for dl_entry in entries:
            child = DownloadFile(
                download_id=download.id,
                parent_id=df.id,
                url=dl_entry.get("url", ""),
                name=dl_entry.get("name"),
                status=FileStatus.QUEUED,
                progress_bytes=0,
                total_bytes=0,
                speed=0,
            )
            db_session.add(child)

        log.info("Expanded folder into %d files", len(entries))


def update_file_progress(df, dl_entries):
    """Update a DownloadFile's progress and status from one or more download entries."""
    total_progress = 0
    total_size = 0
    total_speed = 0
    all_finished = True
    any_error = False
    any_downloading = False
    error_message = None

    for dl_entry in dl_entries:
        total_progress += dl_entry.get("bytesLoaded", 0)
        total_size += dl_entry.get("bytesTotal", 0)
        total_speed += dl_entry.get("speed", 0)

        entry_status = dl_entry.get("status", "")

        if dl_entry.get("finished"):
            pass
        elif "checking file integrity" in entry_status.lower():
            pass
        else:
            all_finished = False

        if entry_status == "Error":
            any_error = True
            error_message = dl_entry.get("error") or "Download error"
        if dl_entry.get("bytesLoaded", 0) > 0:
            any_downloading = True

    df.progress_bytes = total_progress
    df.total_bytes = total_size
    df.speed = total_speed

    if len(dl_entries) == 1:
        df.name = dl_entries[0].get("name") or df.name

    if all_finished:
        df.status = FileStatus.FINISHED
        df.progress_bytes = df.total_bytes or total_size
        df.speed = 0
    elif any_error:
        df.status = FileStatus.FAILED
        df.error_message = error_message
    elif any_downloading and df.status == FileStatus.QUEUED:
        df.status = FileStatus.DOWNLOADING


def submit_pending(manager):
    """Submit queued downloads that haven't been sent to the download engine yet."""
    pending = db_session.query(Download).filter(
        Download.status == DownloadStatus.QUEUED,
        Download.downloading_since.is_(None),
    ).all()

    for download in pending:
        try:
            links = download.links
            log.info("Submitting '%s' (%d links)", download.title, len(links))
            manager.start(links)
            download.downloading_since = datetime.utcnow()
            db_session.commit()
            log.info("Submitted '%s' for download", download.title)
        except Exception as e:
            log.error("Failed to submit '%s': %s", download.title, e)
            download.status = DownloadStatus.FAILED
            download.error_message = f"Failed to submit download: {e}"
            db_session.commit()


def sync_active(manager, mega_downloads):
    """Match download entries to DB records and update state.

    Returns the set of matched DownloadFile.ids for the integrity sweep.
    """
    matched_file_ids = set()

    active = db_session.query(Download).filter(
        Download.status.in_((
            DownloadStatus.QUEUED,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.NEEDS_REVIEW,
            DownloadStatus.PROCESSING,
        ))
    ).all()

    for download in active:
        db_session.refresh(download)
        if download.status == DownloadStatus.CANCELLED:
            continue

        if download.status == DownloadStatus.PROCESSING:
            log.info("Picking up stuck PROCESSING download '%s' — running post_process", download.title)
            lifecycle.post_process(download, manager)
            continue

        initial_matches = match_download_files(mega_downloads, download.top_level_files)

        maybe_expand_folder_files(download, initial_matches)
        db_session.flush()
        db_session.refresh(download)

        file_matches = match_download_files(mega_downloads, download.leaf_files)
        matched_file_ids.update(file_matches.keys())

        for df in download.leaf_files:
            dl_entries = file_matches.get(df.id)
            if dl_entries is not None:
                active_entries = [e for e in dl_entries if e.get("status") != "Pending"]
                if active_entries:
                    update_file_progress(df, active_entries)

        # Refresh metadata every tick. The function is idempotent: it short-
        # circuits when no leaf has a name yet, and respects metadata_source=USER.
        # The previous "only when name changed" guard had a hole: folder expansion
        # populates names directly on creation, so the subsequent per-file update
        # didn't trigger a change — and refresh never ran for folder downloads.
        metadata.refresh(download)

        new_status = lifecycle.derive_download_status(download)

        if new_status == DownloadStatus.DOWNLOADING and download.status == DownloadStatus.QUEUED:
            log.info("Download started: '%s'", download.title)

        if new_status == DownloadStatus.PROCESSING:
            log.info("All files finished for '%s', post-processing", download.title)
            download.status = DownloadStatus.PROCESSING
            db_session.commit()
            lifecycle.post_process(download, manager)
            continue

        if new_status == DownloadStatus.NEEDS_REVIEW and download.status != DownloadStatus.NEEDS_REVIEW:
            log.info("Filenames known for '%s' but metadata confidence is low — awaiting review", download.title)
            download.status = DownloadStatus.NEEDS_REVIEW
            db_session.commit()
            notify_needs_review(download)
            continue

        if new_status == DownloadStatus.FAILED and download.status != DownloadStatus.FAILED:
            download.status = DownloadStatus.FAILED
            download.error_message = "All files failed"
            db_session.commit()
            notify_failure(download)
            continue

        download.status = new_status
        db_session.commit()

    return matched_file_ids


def recheck_folder(download, manager):
    """Re-check a completed folder download for new files.

    Queries the download engine for the current folder contents, diffs by filename
    against existing leaf files, and creates new child DownloadFile records
    for any files not already present. Returns the count of new files added.
    """
    new_count = 0

    for tf in download.top_level_files:
        if not is_folder_url(tf.url):
            continue

        try:
            folder_files = manager.folder_list(tf.url)
        except Exception as e:
            log.error("Failed to list folder '%s': %s", tf.url, e)
            continue

        existing_names = {f.name for f in tf.children if f.name}

        for ff in folder_files:
            name = ff.get("name")
            if not name or name in existing_names:
                continue

            child = DownloadFile(
                download_id=download.id,
                parent_id=tf.id,
                url=ff.get("url", ""),
                name=name,
                status=FileStatus.QUEUED,
                progress_bytes=0,
                total_bytes=0,
                speed=0,
            )
            db_session.add(child)
            new_count += 1

    if new_count > 0:
        db_session.flush()
        db_session.refresh(download)
        new_urls = [
            f.url for f in download.leaf_files
            if f.status == FileStatus.QUEUED and f.url
        ]
        if new_urls:
            try:
                manager.start(new_urls)
            except Exception as e:
                log.error("Failed to submit re-checked files: %s", e)
        download.status = DownloadStatus.DOWNLOADING
        download.downloading_since = datetime.utcnow()
        db_session.commit()
        log.info("Re-check found %d new files for '%s'", new_count, download.title)
    else:
        db_session.commit()

    return new_count


def integrity_sweep(matched_file_ids):
    """Fail any queued/downloading leaf records that have gone missing from the download engine."""
    active = db_session.query(Download).filter(
        Download.status.in_((DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING))
    ).all()

    now = datetime.utcnow()

    for download in active:
        db_session.refresh(download)
        if download.status == DownloadStatus.CANCELLED:
            continue

        if download.downloading_since is None:
            continue

        unmatched_files = [
            f for f in download.leaf_files
            if f.id not in matched_file_ids and f.status not in (FileStatus.FINISHED, FileStatus.FAILED)
        ]
        if not unmatched_files:
            continue

        age = (now - download.downloading_since).total_seconds()
        if age < config.GRACE_PERIOD:
            continue

        for df in unmatched_files:
            log.warning("File '%s' not found in download engine after %ds",
                        df.name or df.url, int(age))
            df.status = FileStatus.FAILED
            df.error_message = "Disappeared from download engine"

        new_status = lifecycle.derive_download_status(download)
        if new_status == DownloadStatus.FAILED:
            download.status = DownloadStatus.FAILED
            download.error_message = "Download disappeared from download engine"
            notify_failure(download)

        db_session.commit()


