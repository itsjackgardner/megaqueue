## 1. Test Infrastructure Setup

- [x] 1.1 Create `megaqueue/requirements-dev.txt` with pytest, pytest-cov, responses, and `-r requirements.txt`
- [x] 1.2 Create `megaqueue/tests/__init__.py` and `megaqueue/tests/conftest.py` with shared fixtures (in-memory DB, Flask test client, mock config)
- [x] 1.3 Verify `pytest` runs from `megaqueue/` directory and discovers the test directory

## 2. Model Tests

- [x] 2.1 Create `megaqueue/tests/test_models.py` — test Download and DownloadFile creation, relationships, and computed properties (progress_bytes, total_bytes, speed, links, file_paths)

## 3. Megabasterd Client Tests

- [x] 3.1 Create `megaqueue/tests/test_megabasterd_client.py` — test all client methods (status, start, stop, pause, resume, clear509, is_reachable) with mocked HTTP responses via `responses` library
- [x] 3.2 Add error/timeout handling tests for connection failures

## 4. Worker Tests

- [x] 4.1 Create `megaqueue/tests/test_worker.py` — test URL normalization (`_normalize_mega_url`) for both old and new MEGA URL formats
- [x] 4.2 Test file matching logic (`_match_megabasterd_files`) with single file, multi-file, and folder-split scenarios
- [x] 4.3 Test status derivation (`_derive_download_status`) — all-finished triggers processing, any-failed triggers failed, grace period for missing downloads
- [x] 4.4 Test `_sync_active_downloads` end-to-end with mocked client and in-memory DB

## 5. Organizer Tests

- [x] 5.1 Create `megaqueue/tests/test_organizer.py` — test movie routing to `{PLEX_MOVIES_DIR}/Title (Year)/` using `tmp_path`
- [x] 5.2 Test TV episode routing with season detection (S##E## pattern) to `{PLEX_TV_DIR}/Title/Season XX/`
- [x] 5.3 Test archive detection (`_is_archive`) for .rar, .zip, .7z, .001 files
- [x] 5.4 Test source directory cleanup after file organization

## 6. Route Tests

- [x] 6.1 Create `megaqueue/tests/test_routes.py` — test GET routes (dashboard, add form, detail, status API) return correct status codes and content
- [x] 6.2 Test POST `/download` creates Download + DownloadFiles and calls megabasterd start

## 7. Agent Documentation

- [x] 7.1 Create `megaqueue/CLAUDE.md` with testing instructions: how to run tests (`cd megaqueue && pytest`), requirement to run tests after changes, requirement to add/update tests for new/modified functionality, and summary of test conventions (fixtures, mocking patterns)

## 8. Notification Tests

- [x] 8.1 Create `megaqueue/tests/test_notifications.py` — test completion and failure notifications format messages correctly and send to ntfy with correct headers/priority
