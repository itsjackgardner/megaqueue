## 1. Database Migration

- [x] 1.1 Add nullable `parent_id` FK column to `DownloadFile` table (references `download_file.id`, cascade delete)
- [x] 1.2 Add self-referential `children` relationship to `DownloadFile` model in `models.py`
- [x] 1.3 Write and test Alembic migration script for the `parent_id` column

## 2. Configuration

- [x] 2.1 Add `FILEBOT_BIN` to `config.py` with default `"filebot"` and `MEGAQUEUE_FILEBOT_BIN` env var support
- [x] 2.2 Add FileBot startup validation in `app.py` — run `filebot --version`, log warning if not accessible (non-fatal)

## 3. FileBot Organizer

- [x] 3.1 Create `filebot_organizer.py` with `organize_download(download, source_paths)` function signature matching old organizer
- [x] 3.2 Implement archive detection (`.rar`, `.zip`, `.7z`, `.001`) in the source file list
- [x] 3.3 Implement `filebot -extract <archive_files> --output <temp_dir>` step when archives are present
- [x] 3.4 Implement `filebot -rename <files> --output <plex_dir> --format "{plex}" --q <title> --action move -non-strict` for movie and TV
- [x] 3.5 Implement stdout parsing to extract final destination paths from FileBot's `[rename] From [...] to [...]` output
- [x] 3.6 Implement fallback directory scan (files newer than pre-invocation timestamp) when stdout parse yields no paths
- [x] 3.7 Implement temp directory cleanup in `finally` block
- [x] 3.8 Raise exception with FileBot stderr on non-zero exit code
- [x] 3.9 Delete `organizer.py`
- [x] 3.10 Remove `patoolib` from `requirements.txt`

## 4. Worker: Folder Expansion

- [x] 4.1 Update `_match_megabasterd_files()` to check for existing child DownloadFile records before creating new ones (idempotency)
- [x] 4.2 When folder-split entries are detected and no children exist, create child DownloadFile records with `parent_id` set to the folder DownloadFile
- [x] 4.3 Update progress tracking to write to child DownloadFile records (not the parent folder record) after expansion
- [x] 4.4 Update `_derive_download_status()` to use child records (not parent) for folder downloads when children exist
- [x] 4.5 Update `_resolve_source_paths()` to read `DownloadFile.name` from leaf records (children if present, otherwise direct records) combined with `MEGABASTERD_DOWNLOAD_DIR`

## 5. Worker: Post-processing Integration

- [x] 5.1 Update `_post_process()` to call `filebot_organizer.organize_download()` instead of `organizer.organize_download()`
- [x] 5.2 Update source path resolution to use `name` field directly (not megabasterd path field lookup)
- [x] 5.3 Update worker imports — remove `organizer`, add `filebot_organizer`
- [x] 5.4 Update worker tests to mock `worker.filebot_organizer` instead of `worker.organize_download`

## 6. UI: Folder File Display

- [x] 6.1 Update `/api/status` JSON endpoint to return child DownloadFile records (not parent) for folder downloads — each child as a separate file entry
- [x] 6.2 Update dashboard template to derive file count from leaf files (children if present, direct records otherwise)
- [x] 6.3 Update download detail view template to show child DownloadFile records individually for folder downloads
- [x] 6.4 Update detail view to fall back to the parent folder record if children don't yet exist (pre-expansion state)

## 7. Tests

- [x] 7.1 Replace `tests/test_organizer.py` with `tests/test_filebot_organizer.py` — mock subprocess calls, test archive detection, path parsing, temp dir cleanup
- [x] 7.2 Add worker tests for folder expansion: first tick creates children, second tick updates them (idempotent)
- [x] 7.3 Add worker tests for `_resolve_source_paths()` using child record names
- [x] 7.4 Update route tests for `/api/status` to assert child file records are returned for folder downloads
- [x] 7.5 Add model tests for `parent_id` cascade delete behavior
