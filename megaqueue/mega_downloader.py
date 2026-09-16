"""In-process MEGA download manager — replaces the MegaBasterd HTTP sidecar.

Runs an asyncio event loop in a daemon thread. The sync worker thread polls
status() on each tick, getting back dicts in the same shape as MegaBasterd's
GET /status response so sync.py needs minimal changes.
"""
import asyncio
import logging
import threading
from pathlib import Path

from megaqueue.megapull import (
    Downloader, MegaAPI, parse_link, FolderLink,
    ProxyPool, MegaError, PermanentMegaError, QuotaExceeded,
)
from megaqueue.megapull.crypto import (
    folder_master_key, decrypt_node_key, fold_file_nodekey, decrypt_attributes,
)
from megaqueue.megapull.folder import parse_folder_response

log = logging.getLogger(__name__)


class MegaDownloadManager:
    """Orchestrates async MEGA downloads from a sync worker thread.

    Public methods (start, cancel, status, folder_list, remove) are safe to call
    from any thread. Downloads run as asyncio Tasks on a dedicated event loop.
    """

    def __init__(self, dest_dir: str, workers: int = 8, proxy_file: str | None = None):
        self._dest_dir = Path(dest_dir)
        self._workers = workers
        self._proxy_pool = self._load_proxies(proxy_file)
        self._lock = threading.Lock()
        self._entries: dict[str, dict] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    def start_loop(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @staticmethod
    def _load_proxies(proxy_file: str | None) -> ProxyPool:
        if not proxy_file:
            return ProxyPool(None)
        path = Path(proxy_file)
        if not path.exists():
            log.warning("Proxy file not found: %s", proxy_file)
            return ProxyPool(None)
        lines = [
            l.strip() for l in path.read_text().splitlines()
            if l.strip() and not l.startswith("#")
        ]
        log.info("Loaded %d proxies from %s", len(lines), proxy_file)
        return ProxyPool(lines)

    def start(self, urls):
        if isinstance(urls, str):
            urls = [u.strip() for u in urls.splitlines() if u.strip()]
        for url in urls:
            norm = url.strip()
            if not norm:
                continue
            with self._lock:
                if norm in self._entries:
                    continue
                self._entries[norm] = {
                    "url": norm,
                    "name": None,
                    "finished": False,
                    "status": "Queued",
                    "bytesLoaded": 0,
                    "bytesTotal": 0,
                    "speed": 0,
                    "error": None,
                    "sourceUrl": None,
                }
            future = asyncio.run_coroutine_threadsafe(
                self._run_download(norm), self._loop,
            )
            future.add_done_callback(lambda f, u=norm: self._on_future_done(f, u))

    def status(self):
        with self._lock:
            downloads = list(self._entries.values())
        return {"running": True, "downloads": downloads}

    def cancel(self, url):
        norm = url.strip()
        with self._lock:
            task = self._tasks.get(norm)
            entry = self._entries.get(norm)
        if task and not task.done():
            self._loop.call_soon_threadsafe(task.cancel)
        if entry:
            with self._lock:
                entry["finished"] = True
                entry["status"] = "Cancelled"

    def remove(self, url):
        norm = url.strip()
        with self._lock:
            self._entries.pop(norm, None)
            self._tasks.pop(norm, None)

    def folder_list(self, url):
        future = asyncio.run_coroutine_threadsafe(
            self._enumerate_folder(url), self._loop,
        )
        return future.result(timeout=60)

    async def _enumerate_folder(self, url):
        parsed = parse_link(url)
        if not isinstance(parsed, FolderLink):
            raise ValueError(f"Not a folder URL: {url}")
        api = MegaAPI()
        try:
            api.set_folder_session(parsed.folder_id)
            nodes = await api.enumerate_folder(parsed.folder_id, parsed.folder_key_b64)
            master = folder_master_key(parsed.folder_key_b64)
            result = []
            for node in nodes:
                if node.get("t") == 0 or "t" not in node:
                    dec_key = node.get("_dec_key")
                    if dec_key is None:
                        continue
                    name = "(unknown)"
                    if node.get("a"):
                        try:
                            attrs = decrypt_attributes(node["a"], dec_key[:16])
                            name = attrs.get("n", name)
                        except Exception:
                            pass
                    result.append({
                        "name": name,
                        "url": url,
                        "size": node.get("s", 0),
                    })
            return result
        finally:
            await api.close()

    async def _run_download(self, url):
        with self._lock:
            entry = self._entries.get(url)
        if entry is None:
            return

        def on_progress(bytes_written, total_bytes, speed):
            with self._lock:
                e = self._entries.get(url)
                if e:
                    e["bytesLoaded"] = bytes_written
                    e["bytesTotal"] = total_bytes
                    e["speed"] = speed
                    e["status"] = "Downloading"

        try:
            dl = Downloader(
                link=url,
                dest_dir=self._dest_dir,
                workers=self._workers,
                proxy_pool=self._proxy_pool,
                on_progress=on_progress,
            )
            task = asyncio.current_task()
            with self._lock:
                self._tasks[url] = task
                entry["status"] = "Starting"

            await dl.run()

            with self._lock:
                e = self._entries.get(url)
                if e:
                    e["finished"] = True
                    e["status"] = "Complete"
                    e["name"] = dl.filename or e["name"]
                    if dl.filesize:
                        e["bytesLoaded"] = dl.filesize
                        e["bytesTotal"] = dl.filesize
                    e["speed"] = 0

        except asyncio.CancelledError:
            with self._lock:
                e = self._entries.get(url)
                if e:
                    e["finished"] = True
                    e["status"] = "Cancelled"
                    e["speed"] = 0
            log.info("Download cancelled: %s", url)

        except Exception as exc:
            with self._lock:
                e = self._entries.get(url)
                if e:
                    e["finished"] = True
                    e["status"] = "Error"
                    e["error"] = str(exc)
                    e["speed"] = 0
            log.error("Download failed for %s: %s", url, exc)

    def _on_future_done(self, future, url):
        exc = future.exception()
        if exc and not isinstance(exc, asyncio.CancelledError):
            log.error("Download task exception for %s: %s", url, exc)

    def shutdown(self):
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
