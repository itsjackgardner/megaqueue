## Why

The custom file organizer duplicates logic (archive extraction, season detection, folder routing) that FileBot handles natively and more robustly. Separately, when a user adds a folder link, the UI only shows the single submitted URL rather than the individual files megabasterd actually downloads — making it impossible to monitor per-file progress for folder downloads.

## What Changes

- Replace `organizer.py` and its `patoolib`/`7z` archive extraction with a `filebot -rename` subprocess call
- Replace the two-phase extract-then-route logic with a single FileBot invocation that receives the known file paths from `DownloadFile` records
- Add a `filebot -extract` pre-pass for archive files before the rename step (FileBot treats extraction and renaming as separate commands)
- Remove `MEGAQUEUE_*` config vars that only served the old organizer routing logic (`PLEX_MOVIES_DIR` and `PLEX_TV_DIR` remain but are passed to FileBot as `--output`)
- Add a `MEGAQUEUE_FILEBOT_BIN` config var (default: `filebot`) for the FileBot executable path
- Update the download detail view and dashboard API to expose individual `DownloadFile` records for folder downloads, not just the originally submitted folder URL
- **BREAKING**: `organizer.py` is removed; `patoolib` dependency dropped

## Capabilities

### New Capabilities
- `filebot-integration`: FileBot subprocess wrapper that replaces `organizer.py` — handles archive extraction, metadata-matched renaming, and moving to Plex directories

### Modified Capabilities
- `file-organizer`: Requirements change from custom Python routing logic to FileBot-delegated organization; archive consolidation, SxxExx regex, and patoolib extraction requirements are removed; FileBot binary availability becomes a startup requirement
- `web-ui`: Dashboard and detail view must show individual `DownloadFile` entries for folder downloads (i.e. the actual files being downloaded, not just the submitted folder URL)

## Impact

- `organizer.py` — deleted
- `worker.py` — `_post_process()` updated to call FileBot subprocess instead of `organize_download()`
- `config.py` — add `FILEBOT_BIN` config var
- `app.py` — startup validation should verify FileBot binary is accessible
- `requirements.txt` — remove `patoolib`; no new Python deps (FileBot is a system binary)
- `templates/` and `/api/status` route — update to expose per-file data for folder downloads
- Tests — organizer tests replaced with FileBot subprocess integration tests (mocked)
