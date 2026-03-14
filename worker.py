import logging
import re
import threading
import time
from pathlib import Path
from datetime import datetime

import config
from models import db_session, Download, DownloadFile
from megabasterd_client import MegabasterdClient
from organizer import organize_download
from notifications import notify_completion, notify_failure

log = logging.getLogger(__name__)


def _normalize_mega_url(url):
    """Extract (id, key) from either mega.nz URL format for comparison.

    Old format: https://mega.nz/#!{id}!{key}
    New format: https://mega.nz/file/{id}#{key}
    Folder file: https://mega.nz/#N!{id}!{key}###n={folderId}
    """
    # Strip ###n= folder suffix if present
    url = re.sub(r"###n=.+$", "", url)
    m = re.match(r"https?://mega\.nz/#[!N]?!?([^!]+)!(.+)", url)
    if m:
        return f"{m.group(1)}#{m.group(2)}"
    m = re.match(r"https?://mega\.nz/file/([^#]+)#(.+)", url)
    if m:
        return f"{m.group(1)}#{m.group(2)}"
    return url


def _extract_folder_id(url):
    """Extract the mega.nz folder ID from a URL.

    Handles two patterns:
    - Folder URL: https://mega.nz/folder/{folderId}#key  -> folderId
    - Per-file URL with suffix: ...###n={folderId}        -> folderId

    Returns None if neither pattern matches.
    """
    m = re.search(r"###n=([^#&]+)", url)
    if m:
        return m.group(1)
    m = re.match(r"https?://mega\.nz/folder/([^#?/]+)", url)
    if m:
        return m.group(1)
    return None


def _match_megabasterd_files(mb_downloads, download_files):
    """Match megabasterd entries to DownloadFile records.

    Uses three-tier matching:
    1. Direct URL match (for single file downloads)
    2. sourceUrl match (forward-compat shim; not currently returned by megabasterd)
    3. Folder-ID match: extract ###n={folderId} from per-file URL, match against
       DownloadFile records with mega.nz/folder/{folderId} URLs

    Returns dict: DownloadFile.id -> list[megabasterd entry].
    A single DownloadFile may match multiple megabasterd entries (folder splits).
    """
    # Build lookup: normalized URL -> DownloadFile
    file_by_norm = {}
    # Build secondary lookup: folder ID -> DownloadFile (for folder URLs only)
    file_by_folder_id = {}
    for df in download_files:
        file_by_norm[_normalize_mega_url(df.url)] = df
        folder_id = _extract_folder_id(df.url)
        if folder_id and "mega.nz/folder/" in df.url:
            file_by_folder_id[folder_id] = df

    matched = {}  # df.id -> list[mb_entry]

    for mb_dl in mb_downloads:
        # Tier 1: match by direct URL
        norm = _normalize_mega_url(mb_dl.get("url", ""))
        df = file_by_norm.get(norm)

        # Tier 2: match by sourceUrl (folder-split entries; not currently returned)
        if df is None:
            source_norm = _normalize_mega_url(mb_dl.get("sourceUrl", ""))
            df = file_by_norm.get(source_norm)

        # Tier 3: match by folder ID extracted from ###n={folderId} suffix
        if df is None:
            folder_id = _extract_folder_id(mb_dl.get("url", ""))
            if folder_id:
                df = file_by_folder_id.get(folder_id)

        if df is not None:
            matched.setdefault(df.id, []).append(mb_dl)

    return matched


def _update_file_from_megabasterd(df, mb_entries):
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

        if not mb_dl.get("finished"):
            all_finished = False

        mb_status = mb_dl.get("status", "")
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

    # For single-entry matches, keep the name
    if len(mb_entries) == 1:
        df.name = mb_entries[0].get("name") or df.name

    if all_finished:
        df.status = "finished"
        df.speed = 0
    elif any_error:
        df.status = "failed"
        df.error_message = error_message
    elif bandwidth_message:
        df.error_message = bandwidth_message
    elif any_downloading and df.status == "queued":
        df.status = "downloading"


def _resolve_source_paths(download, file_matches):
    """Resolve source file paths from megabasterd entries for post-processing.

    Returns list of Path objects for all files to organize.
    """
    download_dir = Path(config.MEGABASTERD_DOWNLOAD_DIR)
    source_paths = []

    for df in download.files:
        entries = file_matches.get(df.id, [])
        if not entries:
            continue

        for mb_dl in entries:
            rel_path = mb_dl.get("path")
            if not rel_path:
                raise ValueError(
                    f"Could not determine download file path from megabasterd "
                    f"for '{mb_dl.get('name', 'unknown')}'"
                )
            source_paths.append(download_dir / rel_path)

    if not source_paths:
        raise FileNotFoundError("No source file paths resolved from megabasterd")

    return source_paths


def _derive_download_status(download):
    """Compute the overall download status from individual file statuses."""
    statuses = [f.status for f in download.files]
    if not statuses:
        return download.status

    if all(s == "finished" for s in statuses):
        return "processing"
    if all(s == "failed" for s in statuses):
        return "failed"
    if any(s in ("downloading", "finished") for s in statuses):
        return "downloading"
    return "queued"


def _post_process(download, client, file_matches):
    """Organize files, send notification, and clear from megabasterd."""
    try:
        source_paths = _resolve_source_paths(download, file_matches)
        final_paths = organize_download(download, source_paths)
        # Update file_path on each DownloadFile with destination paths
        for i, fp in enumerate(final_paths):
            if i < len(download.files):
                download.files[i].file_path = fp
        download.status = "complete"
        db_session.commit()
        notify_completion(download)
    except Exception as e:
        log.error("Post-processing failed for '%s': %s", download.title, e)
        download.status = "failed"
        download.error_message = f"File organization failed: {e}"
        db_session.commit()
        notify_failure(download)

    # Clear finished files from megabasterd — stop both direct URLs and split entry URLs
    stopped_urls = set()
    for df in download.files:
        # Stop the original URL
        if df.url not in stopped_urls:
            try:
                client.stop(df.url, delete=False)
                stopped_urls.add(df.url)
            except Exception:
                pass
        # Also stop any split entry URLs
        for mb_dl in file_matches.get(df.id, []):
            mb_url = mb_dl.get("url", "")
            if mb_url and mb_url not in stopped_urls:
                try:
                    client.stop(mb_url, delete=False)
                    stopped_urls.add(mb_url)
                except Exception:
                    pass


def _sync_active_downloads(client, mb_downloads):
    """Match megabasterd downloads to DB records and update state."""
    matched_file_ids = set()

    active = db_session.query(Download).filter(
        Download.status.in_(("queued", "downloading"))
    ).all()

    for download in active:
        # Pick up cancellations written by Flask
        db_session.refresh(download)
        if download.status == "cancelled":
            continue

        file_matches = _match_megabasterd_files(mb_downloads, download.files)
        matched_file_ids.update(file_matches.keys())

        # Update each matched file (now with list of entries)
        for df in download.files:
            mb_entries = file_matches.get(df.id)
            if mb_entries is not None:
                _update_file_from_megabasterd(df, mb_entries)

        # Derive overall status
        new_status = _derive_download_status(download)

        if new_status == "downloading" and download.status == "queued":
            log.info("Download started: '%s'", download.title)

        if new_status == "processing":
            log.info("All files finished for '%s', post-processing", download.title)
            download.status = "processing"
            db_session.commit()
            _post_process(download, client, file_matches)
            continue

        if new_status == "failed" and download.status != "failed":
            download.status = "failed"
            download.error_message = "All files failed"
            db_session.commit()
            notify_failure(download)
            continue

        download.status = new_status
        db_session.commit()

    return matched_file_ids


def _integrity_sweep(matched_file_ids):
    """Fail any queued/downloading records that have gone missing from megabasterd."""
    active = db_session.query(Download).filter(
        Download.status.in_(("queued", "downloading"))
    ).all()

    now = datetime.utcnow()

    for download in active:
        db_session.refresh(download)
        if download.status == "cancelled":
            continue

        # Check if any files were unmatched
        unmatched_files = [f for f in download.files if f.id not in matched_file_ids and f.status not in ("finished", "failed")]
        if not unmatched_files:
            continue

        # Stamp downloading_since if missing (defensive)
        if download.downloading_since is None:
            download.downloading_since = now
            db_session.commit()
            continue

        age = (now - download.downloading_since).total_seconds()
        if age < config.MEGABASTERD_GRACE_PERIOD:
            continue

        # Mark unmatched files as failed
        for df in unmatched_files:
            log.warning("File '%s' (id=%d) not found in megabasterd after %ds",
                        df.name or df.url, df.id, int(age))
            df.status = "failed"
            df.error_message = "Disappeared from megabasterd"

        # Re-derive download status
        new_status = _derive_download_status(download)
        if new_status == "failed":
            download.status = "failed"
            download.error_message = "Download disappeared from megabasterd"
            notify_failure(download)

        db_session.commit()


def _poll_once(client):
    """Single poll tick: fetch megabasterd status, sync DB, sweep for stuck records."""
    try:
        status = client.status()
    except Exception as e:
        log.warning("Failed to poll megabasterd status: %s", e)
        return

    mb_downloads = status.get("downloads", [])

    matched_file_ids = _sync_active_downloads(client, mb_downloads)
    _integrity_sweep(matched_file_ids)


def _worker_loop(client):
    """Main worker loop — polls megabasterd on an interval."""
    while True:
        try:
            _poll_once(client)
        except Exception as e:
            log.error("Worker poll error: %s", e)
        finally:
            db_session.remove()
        time.sleep(config.MEGABASTERD_POLL_INTERVAL)


def start_worker():
    """Start the background download worker thread."""
    client = MegabasterdClient()

    if not client.is_reachable():
        log.error(
            "Megabasterd API not reachable at %s — is megabasterd running with the API enabled?",
            config.MEGABASTERD_API_URL,
        )
    else:
        log.info("Megabasterd API connected at %s", config.MEGABASTERD_API_URL)

    thread = threading.Thread(target=_worker_loop, args=(client,), daemon=True)
    thread.start()
    return thread
