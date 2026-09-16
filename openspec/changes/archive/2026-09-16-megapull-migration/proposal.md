## Why

MegaQueue currently depends on MegaBasterd — a forked Java app running as a separate process with a REST API — for all mega.nz downloads. This architecture has three problems:

1. **Java sidecar overhead**: MegaBasterd runs in its own JVM alongside the Python app, consuming 300-500MB RAM on a small NUC. Two processes to deploy, monitor, and update.
2. **Windows-only deployment**: The current setup runs on a Windows 10 NUC using a Python venv and PowerShell scripts. Moving to a homelab Debian 13 server requires re-platforming.
3. **No containerisation**: Without Docker, deployment is fragile (manual venv management, path assumptions, process supervision via Task Scheduler).

The target state is a single Docker container running on Debian 13 that handles mega.nz downloads natively in Python.

## What Changes

- **Replace MegaBasterd with megapull**: Vendor the [megapull](https://github.com/megapull/megapull) Python async library (~500 lines, 8 files) into the megaqueue package. Build a `MegaDownloadManager` orchestration layer that preserves the existing polling architecture — the worker thread polls an in-process manager instead of an HTTP API, and status dicts keep the same shape so `sync.py` needs minimal changes.
- **Fix Windows-specific code for Linux**: Update path handling (env vars instead of hardcoded Windows paths), adjust organiser retry logic (WinError 32 → general retry), drop PowerShell scripts.
- **Containerise with Docker**: Dockerfile + docker-compose.yml. Single container, SQLite volume mount, Plex library bind mounts, `.env` for configuration.
- **Flatten the repo**: The `megaqueue-dev` monorepo wrapper coordinated megaqueue + megabasterd submodules. With megabasterd gone, the `megaqueue` repo becomes the standalone primary repo. `openspec/` moves into it, `megaqueue-dev` is archived.

## Capabilities

### New Capabilities

- `mega-download-manager`: In-process Python download manager wrapping vendored megapull. Manages concurrent downloads, exposes status polling, supports cancellation, progress tracking, folder enumeration, and proxy rotation.
- `docker-deployment`: Dockerfile and docker-compose.yml for single-container deployment on Linux with SQLite persistence and Plex library bind mounts.

### Modified Capabilities

- `download-engine`: Worker thread polls `MegaDownloadManager` instead of MegaBasterd HTTP API. Same polling interval, same status dict shape, same three-tier matching. Config vars renamed from `MEGABASTERD_*` to unprefixed (`DOWNLOAD_DIR`, `POLL_INTERVAL`, `GRACE_PERIOD`).
- `configuration`: Remove `MEGABASTERD_API_URL`. Rename `MEGABASTERD_DOWNLOAD_DIR` → `DOWNLOAD_DIR`, `MEGABASTERD_POLL_INTERVAL` → `POLL_INTERVAL`, `MEGABASTERD_GRACE_PERIOD` → `GRACE_PERIOD`. Add `PROXY_FILE` (optional path to proxy list), `DOWNLOAD_WORKERS` (concurrent chunk workers, default 8).
- `file-organizer`: Remove Windows-specific `WinError 32` retry comment (keep general retry logic, reduce retries from 6 to 3). Path sanitisation already uses `pathlib` and works cross-platform.
- `testing`: Replace `test_megabasterd_client.py` with `test_mega_downloader.py`. Update worker/sync/lifecycle test mocks from `MegabasterdClient` to `MegaDownloadManager`. Add integration test for the async/sync bridge.
- `web-ui`: Remove `clear509` route (MegaBasterd-specific 509 bandwidth workaround). Update cancel route to use `MegaDownloadManager.cancel()`. Remove megabasterd reachability checks from UI.

### Removed Capabilities

- `megabasterd-client`: The HTTP client for MegaBasterd's REST API (`megabasterd_client.py`) is deleted entirely.

## Impact

- **megaqueue Python package**: Major changes to `worker.py`, `sync.py`, `lifecycle.py`, `app.py`, `config.py`. New `mega_downloader.py` and `megapull/` vendored package. Delete `megabasterd_client.py`.
- **Tests**: Rewrite mocks for all modules that touched MegaBasterd. New tests for download manager and async bridge.
- **Configuration**: All `MEGABASTERD_*` env vars renamed or removed. New vars added.
- **Deployment**: Dockerfile, docker-compose.yml, `.env.example` added. PowerShell scripts dropped.
- **Repo structure**: `megaqueue` repo becomes standalone. `megaqueue-dev` archived. `openspec/` moves into `megaqueue`.
- **No data model changes**: SQLAlchemy models and database schema are unchanged.
- **No breaking changes to download data**: In-flight downloads will need to be restarted (MegaBasterd state doesn't migrate), but the database records are preserved.
