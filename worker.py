import logging
import re
import threading
import time

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


def _process_download(client, download):
    """Submit a download to megabasterd and poll until complete or failed."""
    links = download.links
    log.info("Submitting %d link(s) for '%s' to megabasterd", len(links), download.title)

    try:
        client.start(links)
    except Exception as e:
        download.status = "failed"
        download.error_message = f"Failed to submit to megabasterd: {e}"
        db_session.commit()
        return

    download.status = "downloading"
    db_session.commit()

    # Poll for completion
    while True:
        time.sleep(config.MEGABASTERD_POLL_INTERVAL)

        try:
            status = client.status()
        except Exception as e:
            log.warning("Failed to poll megabasterd status: %s", e)
            continue

        mb_downloads = status.get("downloads", [])
        link_set = set(links)
        mb_dl = _find_megabasterd_download(mb_downloads, link_set)

        if mb_dl is None:
            # Download not found in megabasterd — may have been removed externally
            # Check if we ever saw progress; if not, it might still be queuing
            if download.progress_bytes > 0:
                download.status = "failed"
                download.error_message = "Download disappeared from megabasterd"
                db_session.commit()
                return
            continue

        _update_progress(download, mb_dl)
        db_session.commit()

        mb_status = mb_dl.get("status", "")

        if mb_dl.get("finished"):
            log.info("Download complete: '%s'", download.title)
            download.status = "processing"
            db_session.commit()
            _post_process(download, mb_dl)
            return

        if mb_status == "Error":
            download.status = "failed"
            download.error_message = mb_dl.get("error") or "Unknown megabasterd error"
            db_session.commit()
            notify_failure(download)
            return

        if mb_status == "509 Bandwidth Limit Exceeded":
            download.error_message = (
                f"509 Bandwidth Limit — {mb_dl.get('error509Count', 0)} workers affected. "
                "Use 'Clear 509' to retry with fresh proxies."
            )
            db_session.commit()

        # Check if download was cancelled by user
        db_session.refresh(download)
        if download.status == "cancelled":
            log.info("Download cancelled by user: '%s'", download.title)
            try:
                for link in links:
                    client.stop(link, delete=True)
            except Exception:
                pass
            return


def _post_process(download, mb_dl):
    """Organize files and send notification after download completes."""
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


def _worker_loop(client):
    """Main worker loop — picks queued downloads and processes them."""
    while True:
        try:
            download = (
                db_session.query(Download)
                .filter(Download.status == "queued")
                .order_by(Download.created_at)
                .first()
            )

            if download is None:
                time.sleep(2)
                continue

            log.info("Processing download: '%s' (id=%d)", download.title, download.id)
            try:
                _process_download(client, download)
            except Exception as e:
                log.error("Unexpected error processing download %d: %s", download.id, e)
                try:
                    download.status = "failed"
                    download.error_message = f"Unexpected error: {e}"
                    db_session.commit()
                except Exception:
                    db_session.rollback()
        except Exception as e:
            log.error("Worker loop error: %s", e)
            time.sleep(5)
        finally:
            db_session.remove()


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
