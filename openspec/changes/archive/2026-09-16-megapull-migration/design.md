## Context

MegaQueue's download engine currently works by polling a MegaBasterd Java process over HTTP every 5 seconds. The worker thread calls `MegabasterdClient.status()` to get download progress, `client.start(urls)` to submit new downloads, `client.stop(url)` to cancel, and `client.folder_list(url)` to enumerate folder contents. The status response returns a list of dicts with `url`, `name`, `finished`, `progress`, `total_bytes`, `speed`, and optionally `sourceUrl` for folder-split entries.

megapull is a Python async library that downloads from mega.nz using httpx + asyncio + AES-CTR decryption. Its core is `Downloader(link, dest_dir, workers, proxies).run()` — an async coroutine that downloads one file to completion. It has no polling API, no progress callbacks, no cancellation API, and its proxy pool isn't wired into download workers. These gaps must be filled by the orchestration layer.

The key constraint is preserving the polling architecture: `sync.py` expects to receive status dicts in a specific shape and match them against database records using three-tier URL matching. Rather than rewrite `sync.py`, we build `MegaDownloadManager` to emit compatible status dicts.

## Goals / Non-Goals

**Goals:**
- Replace MegaBasterd with an in-process Python download manager, eliminating the Java sidecar
- Preserve the polling architecture so sync.py/lifecycle.py changes are minimal (rename-level, not rewrite-level)
- Support folder enumeration, concurrent downloads, cancellation, and per-file progress reporting
- Containerise the application for Debian 13 deployment
- Flatten the repo structure (megaqueue becomes standalone)

**Non-Goals:**
- Automatic proxy rotation on quota errors (future enhancement — proxy pool is wired but rotation policy is manual)
- Download resume across container restarts (megapull has resume sidecar state files but wiring them is a future enhancement)
- Migrating in-flight MegaBasterd downloads (users restart downloads after migration)
- Web UI redesign (same UI, just remove MegaBasterd-specific elements like clear509)
- Async Flask migration (keep synchronous Flask + waitress, bridge to async via a dedicated event loop thread)

## Decisions

### 1. Async/sync bridge via a dedicated event loop thread

**Decision**: Run a persistent `asyncio` event loop in a daemon thread. `MegaDownloadManager` uses `asyncio.run_coroutine_threadsafe()` to submit downloads and `loop.call_soon_threadsafe()` for cancellation. The worker thread polls the manager's state dict (protected by a threading lock) on each tick.

**Rationale**: Flask + waitress are synchronous. Rewriting to async Flask or Quart is out of scope. A dedicated loop thread is the standard bridge pattern — it's safe, well-understood, and lets megapull's httpx/asyncio code run natively without sync wrappers.

**Alternative rejected**: `asyncio.run()` per download — would create/destroy event loops and prevent concurrent downloads sharing an httpx connection pool.

### 2. MegaDownloadManager emits MegaBasterd-compatible status dicts

**Decision**: The manager maintains a `dict[str, DownloadEntry]` keyed by normalized mega.nz URL. Each entry has `url`, `name`, `finished`, `progress`, `total_bytes`, `speed`, and `sourceUrl` (for folder-expanded files). The `status()` method returns this in the same shape as MegaBasterd's `GET /status` response.

**Rationale**: sync.py's `match_megabasterd_files()` and `update_file_from_megabasterd()` do three-tier matching and progress updates against this dict shape. By preserving it, these functions only need renames (megabasterd → mega), not logic changes. The status dict is the API contract between the download engine and the sync layer.

### 3. Progress tracking via injected callback in megapull's download loop

**Decision**: Modify megapull's `Downloader._download_file()` to accept an optional `on_progress(bytes_written, total_bytes, speed)` callback. The manager passes a callback that updates the entry's progress fields. The callback is called after each chunk write (16 MiB chunks, ~8 workers).

**Rationale**: megapull uses rich.Progress for its TUI, which we're stripping. The progress callback replaces it with a machine-readable interface. Injecting at the chunk level gives ~128 updates per 1GB file (16 MiB chunks) — granular enough for the 5-second poll interval.

**Alternative rejected**: Polling file size on disk — adds filesystem overhead, doesn't give speed, and doesn't work before the first chunk lands.

### 4. Cancellation via asyncio.Task.cancel()

**Decision**: Each download runs as an `asyncio.Task`. Cancellation calls `task.cancel()`, which raises `CancelledError` inside megapull's download coroutine. The manager catches it and marks the entry as finished with an error state. Partial files are cleaned up.

**Rationale**: asyncio's native cancellation is the right tool here. megapull already uses `async with` for httpx clients, so cleanup is handled by context manager `__aexit__`. No need for a custom cancellation token.

### 5. Folder enumeration via megapull's MegaAPI

**Decision**: `MegaDownloadManager.folder_list(url)` calls `MegaAPI.enumerate_folder()` to get folder contents. Returns the same `[{name, url, size}]` format as MegaBasterd's `/folder-list` endpoint. For folder downloads, the manager starts individual downloads for each file, each with `sourceUrl` set to the original folder URL.

**Rationale**: megapull already has `MegaAPI` with `enumerate_folder()` and link parsing for folder URLs. This replaces the Java-side folder listing without adding a new dependency.

### 6. Proxy pool wired but not auto-rotating

**Decision**: `MegaDownloadManager` accepts an optional `proxy_file` path. If provided, it loads proxies into megapull's `ProxyPool` and passes them to download workers. The pool has weighted random selection and auto-ejection of failed proxies. Auto-rotation on quota errors (509) is not implemented in this change — it's a future enhancement.

**Rationale**: megapull's `ProxyPool` exists but isn't wired into `Downloader._download_file()`. Wiring it in covers the common case (use proxies for all downloads). Automatic rotation on 509 errors requires intercepting megapull's error handling at the HTTP layer, which is a deeper change.

### 7. Config renames, not env var aliasing

**Decision**: Rename config vars directly: `MEGABASTERD_DOWNLOAD_DIR` → `MEGAQUEUE_DOWNLOAD_DIR`, `MEGABASTERD_POLL_INTERVAL` → `MEGAQUEUE_POLL_INTERVAL`, `MEGABASTERD_GRACE_PERIOD` → `MEGAQUEUE_GRACE_PERIOD`. Remove `MEGABASTERD_API_URL`. Add `MEGAQUEUE_PROXY_FILE`, `MEGAQUEUE_DOWNLOAD_WORKERS`. No backward-compatible aliases.

**Rationale**: Clean break. There's one deployment (the user's homelab), so there's no migration burden — just update the `.env` file.

### 8. Single-stage Dockerfile with waitress

**Decision**: Single-stage Dockerfile based on `python:3.12-slim`. Install `unrar` via apt (needed for rar extraction). Copy requirements.txt, install deps, copy app. Entrypoint runs `python run.py` (waitress). docker-compose.yml mounts SQLite database, download dir, and Plex library paths as bind mounts.

**Rationale**: waitress is already the WSGI server. No need for gunicorn or nginx — this is a single-user homelab app. Single-stage keeps the Dockerfile simple. `python:3.12-slim` is ~150MB, plus `unrar` and Python deps.

### 9. megapull vendored into megaqueue/megapull/

**Decision**: Copy megapull's 8 source files into `megaqueue/megapull/`, add `__init__.py`, rewrite bare imports to relative imports. Strip the rich TUI dependency. Modify `Downloader` for progress callbacks and the `ProxyPool` wiring.

**Rationale**: megapull isn't on PyPI, uses bare imports (flat repo layout), and needs heavy modification. Vendoring gives full control. The package is small (~500 lines) so maintenance burden is low.

## Architecture

```
Worker Thread (sync)              Event Loop Thread (async)
┌─────────────────────┐          ┌──────────────────────────┐
│ poll every 5s        │          │ asyncio event loop        │
│   manager.status()  ─┼──lock──→│   DownloadEntry dict      │
│   sync_active(...)   │          │                          │
│   submit_pending()  ─┼──coro──→│   manager.start(urls)     │
│   cancel()          ─┼──coro──→│   task.cancel()           │
│   folder_list()     ─┼──coro──→│   MegaAPI.enumerate()     │
└─────────────────────┘          │                          │
                                 │ Per-download asyncio.Task: │
                                 │   Downloader.run()         │
                                 │     → httpx Range GETs     │
                                 │     → AES-CTR decrypt      │
                                 │     → os.pwrite()          │
                                 │     → on_progress callback │
                                 └──────────────────────────┘
```

## Module Changes

| Module | Change Level | Summary |
|--------|-------------|---------|
| `mega_downloader.py` | **NEW** | `MegaDownloadManager` class — async/sync bridge, status tracking, download lifecycle |
| `megapull/` | **NEW** (vendored) | 8 files + `__init__.py`, modified for progress callbacks, proxy wiring, import rewrites |
| `megabasterd_client.py` | **DELETE** | Replaced entirely by `mega_downloader.py` |
| `worker.py` | Moderate | Replace `MegabasterdClient` with `MegaDownloadManager`. Remove HTTP reachability check. Adjust startup (start event loop thread). |
| `sync.py` | Light | Rename functions (`megabasterd` → `mega`). Same logic — status dict format is compatible. |
| `lifecycle.py` | Light | Rename `_stop_megabasterd_entries()` → `_cancel_active_downloads()`. Replace `client.stop()` with `manager.cancel()`. |
| `app.py` | Light | Remove `clear509` route. Update cancel route to use manager. Remove megabasterd reachability from startup. |
| `config.py` | Light | Rename env vars, add new ones, remove `MEGABASTERD_API_URL`. |
| `organiser.py` | Light | Update `_move()` retry comment (remove WinError 32 reference), reduce retries 6→3. |
| `models.py` | None | No schema changes. |
| `mega_urls.py` | None | Pure URL helpers, no changes. |
| `metadata.py` | None | No changes. |
| `enums.py` | None | No changes. |
| `notifications.py` | None | No changes. |

## Risks / Trade-offs

**[Async bridge complexity]** → The dedicated event loop thread adds a layer of indirection. Bugs in the bridge (forgotten locks, uncaught exceptions in tasks) could cause silent failures. Mitigation: comprehensive tests for the manager, and the bridge pattern is well-established in Python.

**[megapull modification risk]** → Modifying vendored code means we own all bugs. megapull has no test suite. Mitigation: the library is small, we'll add tests for the modified paths, and we can read the original code to understand edge cases.

**[No download resume on restart]** → If the container restarts mid-download, in-progress files are lost. megapull has a resume sidecar (`.megapull.json`) but it's not wired in. Mitigation: acceptable for a homelab — downloads are restartable, and container restarts are rare. Resume is a future enhancement.

**[509 quota errors without auto-rotation]** → mega.nz bandwidth quotas (509 errors) were handled by MegaBasterd's `clear509` (IP rotation). The new system has proxy support but no automatic rotation on 509. Mitigation: the proxy pool supports manual configuration, and 509 errors will surface as download failures that the user can retry. Auto-rotation is a future enhancement.

**[Folder expansion timing]** → MegaBasterd expanded folders server-side and reported individual files. megapull requires explicit `enumerate_folder()` then individual `Downloader()` calls. The expansion happens at submit time rather than being discovered during polling. This changes the timing but not the data flow — child DownloadFile records are still created, just earlier in the lifecycle.
