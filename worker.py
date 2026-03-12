import logging
import re
import threading
import time
from datetime import datetime, timezone

import config
from models import db_session, Download
from megabasterd_client import MegabasterdClient
from organizer import organize_download
from notifications import notify_completion, notify_failure

log = logging.getLogger(__name__)


def _normalize_mega_url(url):
    """Extract (id, key) from either mega.nz URL format for comparison.

    Old format: https://mega.nz/#!{id}!{key}
    New format: https://mega.nz/file/{id}#{key}
    """
    m = re.match(r"https?://mega\.nz/#!([^!]+)!(.+)", url)
    if m:
        return f"{m.group(1)}#{m.group(2)}"
    m = re.match(r"https?://mega\.nz/file/([^#]+)#(.+)", url)
    if m:
        return f"{m.group(1)}#{m.group(2)}"
    return url


def _find_megabasterd_download(mb_downloads, mega_urls):
    """Match a MegaQueue download's URLs against megabasterd's status list."""
    normalized = {_normalize_mega_url(u) for u in mega_urls}
    for mb_dl in mb_downloads:
        if _normalize_mega_url(mb_dl.get("url", "")) in normalized:
            return mb_dl
    return None


def _update_progress(download, mb_dl):
    """Update a MegaQueue download with megabasterd's progress data."""
    download.progress_bytes = mb_dl.get("bytesLoaded", 0)
    download.total_bytes = mb_dl.get("bytesTotal", 0)
    download.speed = mb_dl.get("speed", 0)


def _post_process(download, mb_dl, client):
    """Organize files, send notification, and clear from megabasterd."""
    try:
        file_paths = organize_download(download)
        download.file_paths = file_paths
        download.status = "complete"
        db_session.commit()
        notify_completion(download)
    except Exception as e:
        log.error("Post-processing failed for '%s': %s", download.title, e)
        download.status = "failed"
        download.error_message = f"File organization failed: {e}"
        db_session.commit()
        notify_failure(download)

    # Clear finished download from megabasterd
    try:
        url = mb_dl.get("url")
        if url:
            client.stop(url, delete=False)
    except Exception:
        pass


def _sync_active_downloads(client, mb_downloads):
    """Match megabasterd downloads to DB records and update state."""
    matched_ids = set()

    active = db_session.query(Download).filter(
        Download.status.in_(("queued", "downloading"))
    ).all()

    for download in active:
        # Pick up cancellations written by Flask
        db_session.refresh(download)
        if download.status == "cancelled":
            continue

        mb_dl = _find_megabasterd_download(mb_downloads, set(download.links))
        if mb_dl is None:
            continue

        matched_ids.add(download.id)
        _update_progress(download, mb_dl)

        mb_status = mb_dl.get("status", "")

        # Queued -> downloading when megabasterd starts working on it
        if download.status == "queued" and download.progress_bytes > 0:
            download.status = "downloading"
            log.info("Download started: '%s'", download.title)

        # Completion
        if mb_dl.get("finished"):
            log.info("Download complete: '%s'", download.title)
            download.status = "processing"
            db_session.commit()
            _post_process(download, mb_dl, client)
            continue

        # Error
        if mb_status == "Error":
            download.status = "failed"
            download.error_message = mb_dl.get("error") or "Unknown megabasterd error"
            db_session.commit()
            notify_failure(download)
            continue

        # 509 (non-terminal, just annotate)
        if mb_status == "509 Bandwidth Limit Exceeded":
            download.error_message = (
                f"509 Bandwidth Limit — {mb_dl.get('error509Count', 0)} workers affected. "
                "Use 'Clear 509' to retry with fresh proxies."
            )

        db_session.commit()

    return matched_ids


def _integrity_sweep(matched_ids):
    """Fail any queued/downloading records that have gone missing from megabasterd."""
    active = db_session.query(Download).filter(
        Download.status.in_(("queued", "downloading"))
    ).all()

    now = datetime.now(timezone.utc)

    for download in active:
        db_session.refresh(download)
        if download.status == "cancelled":
            continue

        if download.id in matched_ids:
            continue

        # Stamp downloading_since if missing (defensive)
        if download.downloading_since is None:
            download.downloading_since = now
            db_session.commit()
            continue

        age = (now - download.downloading_since).total_seconds()
        if age < config.MEGABASTERD_GRACE_PERIOD:
            continue

        log.warning("Download '%s' (id=%d) not found in megabasterd after %ds — marking failed",
                     download.title, download.id, int(age))
        download.status = "failed"
        download.error_message = "Download disappeared from megabasterd"
        db_session.commit()
        notify_failure(download)


def _poll_once(client):
    """Single poll tick: fetch megabasterd status, sync DB, sweep for stuck records."""
    try:
        status = client.status()
    except Exception as e:
        log.warning("Failed to poll megabasterd status: %s", e)
        return

    mb_downloads = status.get("downloads", [])

    matched_ids = _sync_active_downloads(client, mb_downloads)
    _integrity_sweep(matched_ids)


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
