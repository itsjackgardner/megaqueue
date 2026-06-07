"""Background worker — drives the poll loop. All actual work lives in `sync` and `lifecycle`."""

import logging
import threading
import time

from megaqueue import config, sync
from megaqueue.megabasterd_client import MegabasterdClient
from megaqueue.models import db_session

log = logging.getLogger(__name__)


def _poll_once(client):
    """Single poll tick: submit pending, fetch megabasterd status, sync DB, sweep."""
    sync.submit_pending(client)

    try:
        status = client.status()
    except Exception as e:
        log.warning("Failed to poll megabasterd status: %s", e)
        return

    mb_downloads = status.get("downloads", [])

    matched_file_ids = sync.sync_active(client, mb_downloads)
    sync.integrity_sweep(matched_file_ids)


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
