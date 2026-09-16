## 1. Megabasterd API Changes

- [x] 1.1 Add `sourceUrl` field to megabasterd's `/status` response — each download entry includes the original URL submitted to `/start`
- [x] 1.2 Add `path` field to megabasterd's `/status` response — relative path from download dir (e.g., `FolderName/file.mkv` for folder contents, `file.mkv` for single files)

## 2. Configuration

- [x] 2.1 Add `MEGABASTERD_DOWNLOAD_DIR` to `config.py` with `_env()` and add it to `_REQUIRED` validation

## 3. Worker: Folder-Split Matching

- [x] 3.1 Update `_match_megabasterd_files` to use two-tier matching: first by normalized URL, then by `sourceUrl` for unmatched entries
- [x] 3.2 Update `_update_file_from_megabasterd` to handle one-to-many matching — aggregate `progress_bytes`, `total_bytes`, and `speed` across all matched entries for a single `DownloadFile`
- [x] 3.3 A folder-split `DownloadFile` is only "finished" when ALL matched megabasterd entries report `finished: true`

## 4. Worker: Source Path Resolution

- [x] 4.1 Before calling `organize_download`, resolve source file paths using `path` field from matched megabasterd entries + `MEGABASTERD_DOWNLOAD_DIR`. Store resolved paths on the download for the organizer to use.
- [x] 4.2 For folder-split downloads, collect all `path` values from matched entries (multiple files per DownloadFile)
- [x] 4.3 Fail the download if any matched entry is missing the `path` field

## 5. Organizer: File Discovery

- [x] 5.1 Rewrite `organize_download` to accept resolved source file paths (not derive them from the Download model). Handle both file paths and directory paths (walk directories to collect all files within).
- [x] 5.2 Handle the case where a source path does not exist on disk (raise `FileNotFoundError` with descriptive message)

## 6. Organizer: Archive Handling

- [x] 6.1 Detect archive files across all collected source files from all source directories
- [x] 6.2 When archive parts exist in multiple source directories, copy them into a single temp directory before extraction
- [x] 6.3 Extract archives (reuse existing `_extract_archives` logic with patool/7z fallback), then combine extracted files with non-archive originals into a single list for routing

## 7. Organizer: File Routing

- [x] 7.1 Route movie files: move all non-archive media files to `<PLEX_MOVIES_DIR>/<Title> (<Year>)/`
- [x] 7.2 Route TV files: analyze each file's name for `SxxExx` pattern and route to the correct `Season XX/` subfolder independently
- [x] 7.3 Return list of all final destination paths from `organize_download`

## 8. Organizer: Cleanup

- [x] 8.1 After all files are successfully moved, delete source files/directories from the megabasterd download directory
- [x] 8.2 Clean up any temp consolidation directories used for archive extraction
- [x] 8.3 If any file move fails, skip cleanup entirely and propagate the error

## 9. Worker: Post-Processing Integration

- [x] 9.1 Update `_post_process` to pass resolved source paths to the rewritten organizer
- [x] 9.2 Update `DownloadFile.file_path` with final destination paths returned by the organizer

## 10. UI: File Destination Display

- [x] 10.1 Update the download detail view to show each file's final destination path (`file_path`) after organization is complete
