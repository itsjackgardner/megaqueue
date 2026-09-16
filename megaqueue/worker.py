"""Background worker — drives the poll loop. All actual work lives in `sync` and `lifecycle`."""

import logging
import threading
import time

from megaqueue import config, sync
from megaqueue.mega_downloader import MegaDownloadManager
from megaqueue.models import db_session

log = logging.getLogger(__name__)


def _poll_once(manager):
    """Single poll tick: submit pending, fetch status, sync DB, sweep."""
    sync.submit_pending(manager)

    try:
        status = manager.status()
    except Exception as e:
        log.warning("Failed to poll download status: %s", e)
        return

    downloads = status.get("downloads", [])

    matched_file_ids = sync.sync_active(manager, downloads)
    sync.integrity_sweep(matched_file_ids)


def _worker_loop(manager):
    """Main worker loop — polls download manager on an interval."""
    while True:
        try:
            _poll_once(manager)
        except Exception as e:
            log.error("Worker poll error: %s", e)
        finally:
            db_session.remove()
        time.sleep(config.POLL_INTERVAL)


def start_worker():
    """Start the background download worker thread."""
    manager = MegaDownloadManager(
        dest_dir=config.DOWNLOAD_DIR,
        workers=config.DOWNLOAD_WORKERS,
        proxy_file=config.PROXY_FILE,
    )
    manager.start_loop()
    log.info("Download manager started (workers=%d)", config.DOWNLOAD_WORKERS)

    thread = threading.Thread(target=_worker_loop, args=(manager,), daemon=True)
    thread.start()
    return thread
