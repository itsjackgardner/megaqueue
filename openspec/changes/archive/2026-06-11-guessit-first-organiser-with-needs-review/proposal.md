## Why

FileBot is paid software and its auto-detection misclassified a movie as a TV episode (the `Birth (2004)` failure). The user-provided form fields (`title`, `year`, `media_type`) duplicate information that's already in the released filenames. We can collapse the submit form to "paste mega.nz links", infer everything from filenames with `guessit` (MIT-licensed, pure Python), and gain a deterministic, free organiser that names files canonically for Plex. When guessit can't resolve confidently, the system holds post-processing in a new `needs_review` state and pings the user via ntfy — clean separation between "your input, then continue" and today's terminal `failed`.

## What Changes

- **BREAKING (UX)**: Submit form drops `title`, `year`, `media_type` fields — accepts only mega.nz links (one or many, newline-separated).
- **BREAKING (model)**: `Download.title` becomes nullable; `Download.year` and `Download.media_type` already optional/nullable. They are populated by guessit after megabasterd reports filenames, not by the user at submit time.
- **NEW**: `metadata_confidence` (enum: `high` | `low`) and `metadata_source` (enum: `guessit` | `user`) columns on `Download`.
- **NEW**: `is_extra` boolean column on `DownloadFile` for files identified as movie featurettes/trailers.
- **NEW**: Add `needs_review` to the `Download.status` enum, slotted between `downloading` and `processing`. Worker enters it when all files are finished but metadata confidence is `low`.
- **NEW**: Hand-rolled organiser replaces FileBot. Movies → `<PLEX_MOVIES_DIR>/<Title> (<Year>)/<Title> (<Year>).<ext>`, extras → `<PLEX_MOVIES_DIR>/<Title> (<Year>)/Featurettes/<original-name>`. TV → `<PLEX_TV_DIR>/<Title>/Season NN/<Title> - S<NN>E<NN>.<ext>`. Archive extraction via `rarfile` + `zipfile` + `py7zr` (pure Python, no system binary except `unrar` for rar archives).
- **NEW**: Guessit runs in the worker on every `DownloadFile.name` populated by megabasterd. Per-file results aggregate into the parent `Download`'s metadata in real time.
- **NEW**: `POST /download/<id>/resolve` route accepts user-supplied title/year/media_type and per-file `is_extra` overrides, then transitions `needs_review` → `processing` so the organiser runs.
- **NEW**: Dashboard and detail view surface guessit-resolved metadata as it lands (no full-page reload — uses existing 5s polling). `needs_review` rows render an inline form for corrections.
- **NEW**: ntfy push fires when a download enters `needs_review`.
- **REMOVED**: FileBot dependency, `MEGAQUEUE_FILEBOT_BIN` config, FileBot startup check.
- **NEW (internal restructure, done first)**: Split `worker.py` (446 LOC, mixed responsibilities) into `mega_urls.py` (pure URL helpers), `sync.py` (megabasterd ↔ DB matching + folder expansion + per-file updates), `lifecycle.py` (status transitions + post-processing orchestration), and a slimmed `worker.py` (poll loop only). Replace status string literals with `enum.StrEnum` classes (`DownloadStatus`, `FileStatus`, `MetadataConfidence`, `MetadataSource`). Extract `init_db()`'s ad-hoc `ALTER TABLE` blocks into a `migrations.py` module with named, ordered migration functions.

## Capabilities

### New Capabilities

- `metadata-resolution`: Filename-driven metadata extraction (guessit), aggregation across files in a folder, movie-vs-extras classification, and confidence scoring.

### Modified Capabilities

- `data-model`: `Download.title` nullable; `Download.status` adds `needs_review`; `Download` gains `metadata_confidence` and `metadata_source`; `DownloadFile` gains `is_extra`.
- `web-ui`: Submit form collapses to a single textarea of links. Dashboard and detail show resolved metadata as it streams in. `needs_review` rows render a resolve form.
- `file-organizer`: Replaced wholesale — guessit-driven naming, no external CLI, archive extraction via Python libs, extras handled via `Featurettes/` subfolder.
- `notifications`: New notification type for `needs_review`.
- `configuration`: Remove `MEGAQUEUE_FILEBOT_BIN`. No new required config.

### Removed Capabilities

- `filebot-integration`: Replaced by `metadata-resolution` + a new hand-rolled organiser. Reason: paid software, opaque auto-detection caused real failures (Birth (2004)), duplicates user-known fields. Migration: existing downloads with `media_type`/`title` already set continue to work — guessit only runs on new downloads or on Retry.

## Impact

- Code (megaqueue submodule):
  - `megaqueue/models.py` — new columns, `StrEnum` status types, migration registration moved to `migrations.py`.
  - `megaqueue/migrations.py` — **new**: named migration functions called in order by `init_db()`.
  - `megaqueue/app.py` — submit route accepts only links; new `/resolve` route; CSRF + form templates.
  - `megaqueue/worker.py` — **slimmed** to the poll loop only; delegates to `sync` and `lifecycle`.
  - `megaqueue/mega_urls.py` — **new**: pure URL helpers (`normalize`, `extract_folder_id`, `is_folder_url`) extracted from `worker.py`.
  - `megaqueue/sync.py` — **new**: megabasterd matching, folder expansion, per-file updates, guessit hook (`metadata.refresh` call).
  - `megaqueue/lifecycle.py` — **new**: status derivation, `needs_review` transition, post-processing orchestration.
  - `megaqueue/filebot_organizer.py` — **deleted**, replaced by `megaqueue/organiser.py` (hand-rolled, modelled on the pre-FileBot version at `469eeca`).
  - `megaqueue/metadata.py` — **new**: guessit wrapping, per-file → Download aggregation, confidence scoring, main-feature-vs-extras detection.
  - `megaqueue/notifications.py` — `notify_needs_review`.
  - `megaqueue/templates/` — index + detail + add forms updated.
  - `requirements.txt` — add `guessit`, `rarfile`, `py7zr`; remove FileBot-related notes.
- Tests: new `test_metadata.py`, `test_organiser.py`, `test_mega_urls.py`, `test_sync.py`, `test_lifecycle.py`, `test_migrations.py`; existing `test_worker.py` shrinks to cover the poll loop only; existing `test_routes.py`/`test_models.py` updated.
- Config: `MEGAQUEUE_FILEBOT_BIN` deleted from `config.py` and parent-repo deployment scripts.
- Specs: deltas on `data-model`, `web-ui`, `file-organizer`, `notifications`, `configuration`; new `metadata-resolution`; removal of `filebot-integration`.
- Deployment: NUC no longer needs FileBot installed; `unrar` (the system binary used by `rarfile`) needs to be available on PATH if any download contains `.rar` archives.
