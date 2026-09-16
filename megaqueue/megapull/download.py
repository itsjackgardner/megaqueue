"""Parallel async MEGA.nz downloader with proxy rotation."""
import asyncio, os, logging
from pathlib import Path
from typing import Callable

from .api import MegaAPI
from .links import parse_link, FileLink, FolderLink, FolderFileLink
from .folder import parse_folder_response
from .crypto import (
    derive_file_key_iv, aes_ctr_decryptor, decrypt_attributes,
    b64url_encode, bytes_to_a32, a32_to_bytes,
    fold_file_nodekey, folder_master_key, decrypt_node_key,
)
from .errors import MegaError, PermanentMegaError, QuotaExceeded
from .proxy import ProxyPool

log = logging.getLogger(__name__)

CHUNK = 16 * 1024 * 1024  # 16 MiB per worker range
WORKERS_DEFAULT = 8


class Downloader:
    def __init__(
        self,
        link: str,
        dest_dir: Path,
        workers: int = WORKERS_DEFAULT,
        proxy_pool: ProxyPool | None = None,
        on_progress: Callable[[int, int, int], None] | None = None,
    ):
        self.link = link
        self.parsed = parse_link(link)
        self.dest_dir = dest_dir
        self.workers = workers
        self.proxy_pool = proxy_pool
        self.on_progress = on_progress
        self.api = MegaAPI()
        self.filename: str | None = None
        self.filesize: int = 0

    async def run(self):
        self.dest_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(self.parsed, FileLink):
            key16, nonce8, mac_seed = derive_file_key_iv(self.parsed.file_key_b64)
            dl = await self.api.get_download_info(self.parsed.file_id, self.parsed.file_key_b64)
            fname = decrypt_attributes(dl["at"], key16)["n"]
            size = dl["s"]
            g_url = dl["g"]
            await self._download_file(fname, size, g_url, key16, nonce8)

        elif isinstance(self.parsed, FolderLink):
            self.api.set_folder_session(self.parsed.folder_id)
            nodes = await self.api.enumerate_folder(self.parsed.folder_id, self.parsed.folder_key_b64)
            if not nodes:
                raise PermanentMegaError("Folder returned no files (link may be empty, deleted, or the key is incorrect)")
            master_key = folder_master_key(self.parsed.folder_key_b64)
            for node in nodes:
                if node.get("t") == 0:
                    enc_key_b64 = node["k"].split(":")[1] if ":" in node["k"] else node["k"]
                    node_key_32 = decrypt_node_key(enc_key_b64, master_key)
                    key16, nonce8, mac_seed = fold_file_nodekey(node_key_32)
                    dl = await self.api.get_node_download(node["h"], self.parsed.folder_key_b64)
                    fname = decrypt_attributes(node["a"], key16)["n"]
                    size = dl["s"]
                    g_url = dl["g"]
                    await self._download_file(fname, size, g_url, key16, nonce8)

        elif isinstance(self.parsed, FolderFileLink):
            master_key = folder_master_key(self.parsed.folder_key_b64)
            node_key_32 = decrypt_node_key(self.parsed.sub_file_key_b64, master_key)
            key16, nonce8, mac_seed = fold_file_nodekey(node_key_32)
            dl = await self.api.get_node_download(self.parsed.sub_file_id, self.parsed.folder_key_b64)
            fname = decrypt_attributes(self.parsed.sub_file_id, key16)["n"]
            size = dl["s"]
            g_url = dl["g"]
            await self._download_file(fname, size, g_url, key16, nonce8)

        await self.api.close()

    async def _download_file(self, fname, size, g_url, key16, nonce8):
        self.filename = fname
        self.filesize = size
        out_path = self.dest_dir / fname
        log.info("Downloading %s (%d bytes)", fname, size)

        fd = os.open(out_path, os.O_CREAT | os.O_RDWR)
        os.ftruncate(fd, size)

        queue: asyncio.Queue = asyncio.Queue()
        for s in range(0, size, CHUNK):
            queue.put_nowait((s, min(s + CHUNK, size)))

        self._bytes_written = 0
        self._speed_bytes = 0

        workers = [
            asyncio.create_task(self._worker(i, queue, g_url, fd, size, key16, nonce8))
            for i in range(self.workers)
        ]
        await queue.join()
        for _ in workers:
            queue.put_nowait(None)
        await asyncio.gather(*workers, return_exceptions=True)

        os.close(fd)
        log.info("Download complete: %s", out_path)

    async def _worker(self, name, queue, g_url, fd, total_size, key16, nonce8):
        import httpx
        proxy_url = None
        proxy_obj = None
        if self.proxy_pool:
            proxy_obj = self.proxy_pool.pick()
            if proxy_obj:
                proxy_url = proxy_obj.url

        async with httpx.AsyncClient(http2=True, proxy=proxy_url) as client:
            while True:
                rng = await queue.get()
                if rng is None:
                    queue.task_done()
                    if proxy_obj and self.proxy_pool:
                        self.proxy_pool.release(proxy_obj, True)
                    return
                start, end = rng
                attempt = 0
                while True:
                    attempt += 1
                    try:
                        headers = {"Range": f"bytes={start}-{end-1}"}
                        async with client.stream("GET", g_url, headers=headers, timeout=httpx.Timeout(60, read=120)) as r:
                            if r.status_code == 403:
                                raise Exception("g-url expired")
                            if r.status_code == 509:
                                if proxy_obj and self.proxy_pool:
                                    self.proxy_pool.release(proxy_obj, False, 509)
                                raise QuotaExceeded("509 Bandwidth Limit Exceeded")
                            r.raise_for_status()
                            block_offset = start // 16
                            dec = aes_ctr_decryptor(key16, nonce8, block_offset)
                            pos = start
                            async for chunk in r.aiter_bytes(262144):
                                plain = dec.update(chunk)
                                os.pwrite(fd, plain, pos)
                                pos += len(plain)
                                self._bytes_written += len(plain)
                                if self.on_progress:
                                    self.on_progress(self._bytes_written, total_size, 0)
                            tail = dec.finalize()
                            if tail:
                                os.pwrite(fd, tail, pos)
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        if attempt > 10:
                            queue.task_done()
                            if proxy_obj and self.proxy_pool:
                                self.proxy_pool.release(proxy_obj, False)
                            raise
                        await asyncio.sleep(min(30, 1.5 ** attempt))
                queue.task_done()
