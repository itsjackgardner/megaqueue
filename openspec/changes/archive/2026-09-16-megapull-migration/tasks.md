## 1. Vendor megapull

- [x] 1.1 Copy megapull source files (`download.py`, `api.py`, `links.py`, `folder.py`, `crypto.py`, `proxy.py`, `state.py`, `errors.py`) into `megaqueue/megapull/`
- [x] 1.2 Create `megaqueue/megapull/__init__.py` with public API exports (`Downloader`, `MegaAPI`, `parse_link`, `ProxyPool`, error classes)
- [x] 1.3 Rewrite bare imports to relative imports across all megapull files (e.g., `from crypto import` → `from .crypto import`)
- [x] 1.4 Strip rich dependency — remove `rich.Progress` usage from `download.py`, replace with optional `on_progress` callback parameter
- [x] 1.5 Wire `ProxyPool` into `Downloader._download_file()` — pass proxy to httpx client per chunk worker
- [x] 1.6 Add `httpx[http2]>=0.27` and `cryptography>=42` to `requirements.txt`

## 2. Build MegaDownloadManager

- [x] 2.1 Create `megaqueue/mega_downloader.py` with `MegaDownloadManager` class: init starts a daemon thread with an asyncio event loop
- [x] 2.2 Implement `start(urls, dest_dir)` — parses URLs, creates `DownloadEntry` per URL, submits `asyncio.Task` per download via `run_coroutine_threadsafe()`
- [x] 2.3 Implement `status()` — returns `{"running": True, "downloads": [...]}` matching MegaBasterd's response shape. Thread-safe read of entry dict (protected by `threading.Lock`)
- [x] 2.4 Implement progress callback — each download task passes `on_progress` to `Downloader`, callback updates entry's `progress`, `total_bytes`, `speed` fields under lock
- [x] 2.5 Implement `cancel(url)` — looks up the asyncio Task by URL, calls `task.cancel()`, marks entry as finished
- [x] 2.6 Implement `folder_list(url)` — calls `MegaAPI.enumerate_folder()` via `run_coroutine_threadsafe()`, returns `[{name, url, size}]`
- [x] 2.7 Implement download completion handling — on task success, mark entry `finished=True`; on exception, mark entry with error; on `CancelledError`, clean up partial files
- [x] 2.8 Implement `remove(url)` — removes a finished entry from the status dict (replaces MegaBasterd's delete-on-stop behavior)

## 3. Adapt worker.py

- [x] 3.1 Replace `MegabasterdClient` instantiation with `MegaDownloadManager` instantiation (pass `dest_dir`, `workers`, `proxy_file` from config)
- [x] 3.2 Remove megabasterd HTTP reachability check loop — manager is always available (in-process)
- [x] 3.3 Update `_poll_once()` to call `manager.status()` instead of `client.status()`
- [x] 3.4 Start the manager's event loop thread in `start_worker()`, ensure it shuts down cleanly on app exit

## 4. Adapt sync.py

- [x] 4.1 Rename `submit_pending(client)` → `submit_pending(manager)` and call `manager.start()` instead of `client.start()`
- [x] 4.2 Rename `sync_active(client, mb_downloads)` → `sync_active(manager, downloads)` and rename internal references
- [x] 4.3 Rename `match_megabasterd_files()` → `match_download_files()` — same three-tier matching logic, same status dict fields
- [x] 4.4 Rename `update_file_from_megabasterd()` → `update_file_progress()` — same field mapping
- [x] 4.5 Update `recheck_folder()` to call `manager.folder_list()` instead of `client.folder_list()`

## 5. Adapt lifecycle.py, app.py, config.py

- [x] 5.1 Rename `_stop_megabasterd_entries()` → `_cancel_active_downloads()` in `lifecycle.py`, call `manager.cancel()` instead of `client.stop()`
- [x] 5.2 Remove `clear509` route from `app.py` and its template link
- [x] 5.3 Update cancel route in `app.py` to use `manager.cancel()` instead of `mb_client.stop()`
- [x] 5.4 Update recheck route in `app.py` to use `manager.folder_list()` instead of `mb_client.folder_list()`
- [x] 5.5 Remove megabasterd reachability banner from dashboard template
- [x] 5.6 Rename config vars in `config.py`: `MEGABASTERD_DOWNLOAD_DIR` → `DOWNLOAD_DIR`, `MEGABASTERD_POLL_INTERVAL` → `POLL_INTERVAL`, `MEGABASTERD_GRACE_PERIOD` → `GRACE_PERIOD`
- [x] 5.7 Remove `MEGABASTERD_API_URL` from config, add `PROXY_FILE` and `DOWNLOAD_WORKERS`
- [x] 5.8 Update all config references across worker.py, sync.py, app.py to use new names

## 6. Delete MegaBasterd artifacts

- [x] 6.1 Delete `megaqueue/megabasterd_client.py`
- [x] 6.2 Delete `tests/test_megabasterd_client.py`
- [x] 6.3 Remove any remaining `megabasterd` imports or references across the codebase

## 7. Windows → Linux cleanups

- [x] 7.1 Update `organiser.py` `_move()`: change WinError 32 retry comment to generic "file lock retry", reduce retries from 6 to 3
- [x] 7.2 Create `.env.example` with Linux paths (`/data/downloads`, `/media/movies`, `/media/tv`) and new config var names
- [x] 7.3 Verify all path handling uses `pathlib.Path` or `os.path` (no hardcoded backslashes or drive letters)

## 8. Docker

- [x] 8.1 Create `Dockerfile`: `python:3.12-slim` base, `apt-get install unrar`, copy requirements + app, `CMD ["python", "run.py"]`
- [x] 8.2 Create `docker-compose.yml`: single service, volume mounts for SQLite DB (`/data/megaqueue.db`), download dir, Plex movies dir, Plex TV dir; `.env` file reference
- [x] 8.3 Create `.dockerignore`: exclude `.git`, `tests/`, `__pycache__`, `*.db`, `.env`
- [x] 8.4 Verify `run.py` binds to `0.0.0.0` (not localhost) for container networking

## 9. Repo flattening

- [x] 9.1 Move `openspec/` from `megaqueue-dev` into the `megaqueue` repo
- [x] 9.2 Merge relevant parts of `megaqueue-dev/CLAUDE.md` into `megaqueue/CLAUDE.md`
- [x] 9.3 Remove git submodule config (`.gitmodules`, submodule entries) from `megaqueue` if present
- [x] 9.4 Verify `megaqueue` repo works standalone (no references to parent repo)

## 10. Tests

- [x] 10.1 Create `tests/test_mega_downloader.py`: test `MegaDownloadManager` status dict shape, start/cancel/folder_list, progress callback updates, thread safety
- [x] 10.2 Update `tests/test_worker.py`: mock `MegaDownloadManager` instead of `MegabasterdClient`, verify poll loop uses `manager.status()`
- [x] 10.3 Update `tests/test_sync.py`: rename function references, verify same matching logic works with new function names
- [x] 10.4 Update `tests/test_lifecycle.py`: verify `_cancel_active_downloads()` calls `manager.cancel()`
- [x] 10.5 Update `tests/test_routes.py`: remove clear509 route test, update cancel/recheck tests to mock manager
- [x] 10.6 Run full test suite and fix any remaining import/naming issues
