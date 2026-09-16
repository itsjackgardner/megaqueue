## 1. Data Model & Migration

- [x] 1.1 Add `ongoing` boolean column (default `false`) to `Download` model in `models.py`
- [x] 1.2 Add named migration in `migrations.py` to add `ongoing` column to existing databases

## 2. Megabasterd Folder List Endpoint

- [x] 2.1 Add `GET /folder-list?url=<encoded-url>` endpoint to megabasterd REST API that returns JSON array of `{name, url, size}` for files in a mega.nz folder
- [x] 2.2 Add `folder_list(url)` method to `megabasterd_client.py` that calls the new endpoint

## 3. Folder Re-check Logic

- [x] 3.1 Add `recheck_folder` function in a new module or in `sync.py` — calls `folder_list`, diffs by filename against existing leaf files, creates new child DownloadFile records, transitions Download to `downloading`
- [x] 3.2 Update `sync.submit_pending` to handle re-checked Downloads — submit only new (queued) file URLs to megabasterd, skipping already-finished files
- [x] 3.3 Update status derivation in `lifecycle.py` to correctly handle mixed finished + queued leaf files on a re-checked Download

## 4. Organiser Changes

- [x] 4.1 Update organiser to skip leaf files that already have `file_path` set (previously organised)
- [x] 4.2 Add destination-exists check — if computed destination path already exists on disk, skip the move and set `file_path` without error

## 5. Ongoing Status

- [x] 5.1 Add `POST /download/<id>/ongoing` route in `app.py` that toggles the `ongoing` flag
- [x] 5.2 Update dashboard query in `app.py` to separate ongoing and non-ongoing downloads
- [x] 5.3 Update dashboard template to render an "Ongoing" section at the top when ongoing downloads exist

## 6. Re-check UI

- [x] 6.1 Add `POST /download/<id>/recheck` route in `app.py` that triggers the re-check logic and redirects with a flash message
- [x] 6.2 Add "Re-check for new files" button on detail page (visible only for `complete` Downloads with folder URLs)
- [x] 6.3 Add ongoing/finished toggle button to dashboard cards and detail page

## 7. Duplicate Detection

- [x] 7.1 Update `POST /download` route to check submitted folder URLs against existing Downloads and show a warning with link to the existing entry
- [x] 7.2 Add confirmation mechanism to allow submitting a duplicate folder URL after seeing the warning

## 8. Tests

- [x] 8.1 Add tests for `folder_list` client method (mocked HTTP)
- [x] 8.2 Add tests for re-check logic: new files detected, no new files, preserves existing file state
- [x] 8.3 Add tests for organiser skip-existing behavior (file_path already set, destination exists on disk)
- [x] 8.4 Add tests for ongoing toggle route and dashboard query separation
- [x] 8.5 Add tests for duplicate folder URL detection on submission
- [x] 8.6 Add test for status derivation with mixed finished + queued files after re-check
