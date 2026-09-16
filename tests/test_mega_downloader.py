from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import threading

import pytest

from megaqueue.mega_downloader import MegaDownloadManager


@pytest.fixture()
def manager(tmp_path):
    m = MegaDownloadManager(dest_dir=str(tmp_path), workers=2)
    m.start_loop()
    yield m
    m.shutdown()


class TestStatusShape:
    def test_status_returns_running_and_downloads(self, manager):
        result = manager.status()
        assert result["running"] is True
        assert isinstance(result["downloads"], list)

    def test_status_empty_when_no_downloads(self, manager):
        assert manager.status()["downloads"] == []


class TestStartAndEntries:
    def test_start_creates_entry_with_correct_shape(self, manager):
        with patch.object(manager, "_loop") as mock_loop:
            mock_future = MagicMock()
            mock_loop.call_soon_threadsafe = MagicMock()
            with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
                manager.start(["https://mega.nz/file/abc#key1"])

        entries = manager.status()["downloads"]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["url"] == "https://mega.nz/file/abc#key1"
        assert entry["name"] is None
        assert entry["finished"] is False
        assert entry["bytesLoaded"] == 0
        assert entry["bytesTotal"] == 0
        assert entry["speed"] == 0
        assert entry["error"] is None
        assert entry["sourceUrl"] is None
        assert entry["status"] == "Queued"

    def test_start_deduplicates_urls(self, manager):
        with patch("asyncio.run_coroutine_threadsafe", return_value=MagicMock()):
            manager.start(["https://mega.nz/file/abc#key1"])
            manager.start(["https://mega.nz/file/abc#key1"])

        assert len(manager.status()["downloads"]) == 1

    def test_start_accepts_string(self, manager):
        with patch("asyncio.run_coroutine_threadsafe", return_value=MagicMock()):
            manager.start("https://mega.nz/file/abc#key1\nhttps://mega.nz/file/def#key2")

        assert len(manager.status()["downloads"]) == 2


class TestCancel:
    def test_cancel_marks_entry_finished(self, manager):
        with patch("asyncio.run_coroutine_threadsafe", return_value=MagicMock()):
            manager.start(["https://mega.nz/file/abc#key1"])

        manager.cancel("https://mega.nz/file/abc#key1")

        entries = manager.status()["downloads"]
        assert len(entries) == 1
        assert entries[0]["finished"] is True
        assert entries[0]["status"] == "Cancelled"

    def test_cancel_nonexistent_url_is_noop(self, manager):
        manager.cancel("https://mega.nz/file/nonexistent#key")


class TestRemove:
    def test_remove_deletes_entry(self, manager):
        with patch("asyncio.run_coroutine_threadsafe", return_value=MagicMock()):
            manager.start(["https://mega.nz/file/abc#key1"])

        manager.remove("https://mega.nz/file/abc#key1")
        assert manager.status()["downloads"] == []

    def test_remove_nonexistent_url_is_noop(self, manager):
        manager.remove("https://mega.nz/file/nonexistent#key")


class TestProgressCallback:
    def test_progress_callback_updates_entry(self, manager):
        url = "https://mega.nz/file/abc#key1"
        with manager._lock:
            manager._entries[url] = {
                "url": url, "name": None, "finished": False,
                "status": "Queued", "bytesLoaded": 0, "bytesTotal": 0,
                "speed": 0, "error": None, "sourceUrl": None,
            }

        with manager._lock:
            e = manager._entries[url]
            e["bytesLoaded"] = 500
            e["bytesTotal"] = 1000
            e["speed"] = 100
            e["status"] = "Downloading"

        entry = manager.status()["downloads"][0]
        assert entry["bytesLoaded"] == 500
        assert entry["bytesTotal"] == 1000
        assert entry["speed"] == 100
        assert entry["status"] == "Downloading"


class TestLoadProxies:
    def test_load_proxies_returns_empty_pool_when_none(self):
        pool = MegaDownloadManager._load_proxies(None)
        assert pool is not None

    def test_load_proxies_returns_empty_pool_for_missing_file(self):
        pool = MegaDownloadManager._load_proxies("/nonexistent/proxy.txt")
        assert pool is not None

    def test_load_proxies_reads_file(self, tmp_path):
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://proxy1:8080\n# comment\nhttp://proxy2:8080\n")
        pool = MegaDownloadManager._load_proxies(str(proxy_file))
        assert pool is not None


class TestShutdown:
    def test_shutdown_stops_loop(self, tmp_path):
        m = MegaDownloadManager(dest_dir=str(tmp_path), workers=1)
        m.start_loop()
        assert m._loop.is_running()
        m.shutdown()
        assert not m._loop.is_running()

    def test_shutdown_before_start_is_noop(self, tmp_path):
        m = MegaDownloadManager(dest_dir=str(tmp_path), workers=1)
        m.shutdown()
