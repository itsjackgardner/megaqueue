"""megabasterd ↔ DB sync: match status entries to records, expand folders, update per-file state."""

import logging
from datetime import datetime

from megaqueue import config, lifecycle, metadata
from megaqueue.enums import DownloadStatus, FileStatus
from megaqueue.mega_urls import normalize, extract_folder_id, is_folder_url
from megaqueue.models import db_session, Download, DownloadFile
from megaqueue.notifications import notify_failure, notify_needs_review

log = logging.getLogger(__name__)


def match_megabasterd_files(mb_downloads, download_files):
    """Match megabasterd entries to DownloadFile records.

    Uses three-tier matching:
    1. Direct URL match (for single file downloads)
    2. sourceUrl match (for folder-split entries — megabasterd returns the
       original folder URL as sourceUrl on each per-file entry)
    3. Folder-ID match: extract ###n={folderId} from per-file URL, match against
       DownloadFile records whose URL is a recognised folder URL with the same
       folder ID (new or old format).

    Returns dict: DownloadFile.id -> list[megabasterd entry].
    A single DownloadFile may match multiple megabasterd entries (folder splits).
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

    for mb_dl in mb_downloads:
        norm = normalize(mb_dl.get("url", ""))
        df = file_by_norm.get(norm)

        if df is None:
            source_url = mb_dl.get("sourceUrl", "")
            if source_url:
                df = file_by_url.get(source_url)
                if df is None:
                    df = file_by_norm.get(normalize(source_url))

        if df is None:
            folder_id = extract_folder_id(mb_dl.get("url", ""))
            if folder_id:
                df = file_by_folder_id.get(folder_id)

        if df is not None:
            matched.setdefault(df.id, []).append(mb_dl)

    return matched


def maybe_expand_folder_files(download, initial_matches):
    """Expand folder-URL DownloadFiles into per-file child records.

    When a folder URL DownloadFile matches multiple megabasterd entries (folder split)
    and has no existing children, creates one child DownloadFile per megabasterd entry.
    The children track individual file progress; the parent becomes a container.

    Idempotent: skips files that already have children.
    """
    for df in list(download.top_level_files):
        if df.children:
            continue
        mb_entries = initial_matches.get(df.id, [])
        mb_entries = [e for e in mb_entries if e.get("status") != "Pending"]
        if not mb_entries:
            continue
        if not is_folder_url(df.url):
            continue

        for mb_dl in mb_entries:
            child = DownloadFile(
                download_id=download.id,
                parent_id=df.id,
                url=mb_dl.get("url", ""),
                name=mb_dl.get("name"),
                status=FileStatus.QUEUED,
                progress_bytes=0,
                total_bytes=0,
                speed=0,
            )
            db_session.add(child)

        log.info(
            "Expanded folder '%s' into %d child DownloadFile records",
            df.url,
            len(mb_entries),
        )


def update_file_from_megabasterd(df, mb_entries):
    """Update a DownloadFile's progress and status from one or more megabasterd entries."""
    total_progress = 0
    total_size = 0
    total_speed = 0
    all_finished = True
    any_error = False
    any_downloading = False
    error_message = None
    bandwidth_message = None

    for mb_dl in mb_entries:
        total_progress += mb_dl.get("bytesLoaded", 0)
        total_size += mb_dl.get("bytesTotal", 0)
        total_speed += mb_dl.get("speed", 0)

        mb_status = mb_dl.get("status", "")

        if mb_dl.get("finished"):
            pass
        elif "checking file integrity" in mb_status.lower():
            pass
        else:
            all_finished = False

        if mb_status == "Error":
            any_error = True
            error_message = mb_dl.get("error") or "Unknown megabasterd error"
        elif mb_status == "509 Bandwidth Limit Exceeded":
            bandwidth_message = (
                f"509 Bandwidth Limit — {mb_dl.get('error509Count', 0)} workers affected. "
                "Use 'Clear 509' to retry with fresh proxies."
            )
        if mb_dl.get("bytesLoaded", 0) > 0:
            any_downloading = True

    df.progress_bytes = total_progress
    df.total_bytes = total_size
    df.speed = total_speed

    if len(mb_entries) == 1:
        df.name = mb_entries[0].get("name") or df.name

    if all_finished:
        df.status = FileStatus.FINISHED
        df.progress_bytes = df.total_bytes or total_size
        df.speed = 0
    elif any_error:
        df.status = FileStatus.FAILED
        df.error_message = error_message
    elif bandwidth_message:
        df.error_message = bandwidth_message
    elif any_downloading and df.status == FileStatus.QUEUED:
        df.status = FileStatus.DOWNLOADING


def submit_pending(client):
    """Submit queued downloads that haven't been sent to megabasterd yet."""
    pending = db_session.query(Download).filter(
        Download.status == DownloadStatus.QUEUED,
        Download.downloading_since.is_(None),
    ).all()

    for download in pending:
        try:
            links = download.links
            log.info("Submitting '%s' to megabasterd (%d links)", download.title, len(links))
            client.start(links)
            download.downloading_since = datetime.utcnow()
            db_session.commit()
            log.info("Submitted '%s' to megabasterd", download.title)
        except Exception as e:
            log.error("Failed to submit '%s' to megabasterd: %s", download.title, e)
            download.status = DownloadStatus.FAILED
            download.error_message = f"Failed to submit to megabasterd: {e}"
            db_session.commit()


def sync_active(client, mb_downloads):
    """Match megabasterd downloads to DB records and update state.

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

        # Recovery: a download stuck in PROCESSING means post-processing never
        # completed (e.g. the resolve route flipped it to PROCESSING but no tick
        # ran the organiser, or the process was killed mid-organise). Re-run.
        # post_process always exits PROCESSING (to COMPLETE or FAILED), so this
        # cannot loop.
        if download.status == DownloadStatus.PROCESSING:
            log.info("Picking up stuck PROCESSING download '%s' — running post_process", download.title)
            lifecycle.post_process(download, client)
            continue

        initial_matches = match_megabasterd_files(mb_downloads, download.top_level_files)

        maybe_expand_folder_files(download, initial_matches)
        db_session.flush()
        db_session.refresh(download)

        file_matches = match_megabasterd_files(mb_downloads, download.leaf_files)
        matched_file_ids.update(file_matches.keys())

        for df in download.leaf_files:
            mb_entries = file_matches.get(df.id)
            if mb_entries is not None:
                active_entries = [e for e in mb_entries if e.get("status") != "Pending"]
                if active_entries:
                    update_file_from_megabasterd(df, active_entries)

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
            lifecycle.post_process(download, client)
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


def integrity_sweep(matched_file_ids):
    """Fail any queued/downloading leaf records that have gone missing from megabasterd."""
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
        if age < config.MEGABASTERD_GRACE_PERIOD:
            continue

        for df in unmatched_files:
            log.warning("File '%s' (id=%d) not found in megabasterd after %ds",
                        df.name or df.url, df.id, int(age))
            df.status = FileStatus.FAILED
            df.error_message = "Disappeared from megabasterd"

        new_status = lifecycle.derive_download_status(download)
        if new_status == DownloadStatus.FAILED:
            download.status = DownloadStatus.FAILED
            download.error_message = "Download disappeared from megabasterd"
            notify_failure(download)

        db_session.commit()


