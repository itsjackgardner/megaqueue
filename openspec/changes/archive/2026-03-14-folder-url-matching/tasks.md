## 1. Worker: Folder-ID Matching

- [x] 1.1 Add `_extract_folder_id(url)` helper that returns the folder ID from either a `mega.nz/folder/{id}#key` URL or a `###n={folderId}` suffix in a per-file URL (returns `None` if neither pattern matches)
- [x] 1.2 In `_match_megabasterd_files()`, build a secondary lookup dict `file_by_folder_id: {folderId → DownloadFile}` for all DownloadFiles whose URL matches `mega.nz/folder/`
- [x] 1.3 Add Tier 3 in the per-entry matching loop: if Tier 1 and Tier 2 both miss, extract folder ID from the megabasterd entry URL via `_extract_folder_id()` and look it up in `file_by_folder_id`

## 2. Tests

- [x] 2.1 Add unit tests for `_extract_folder_id()` covering: `mega.nz/folder/{id}#key`, `###n={id}` suffix URL, plain file URL (returns None), empty string (returns None)
- [x] 2.2 Add a test for `_match_megabasterd_files()` with a folder URL `DownloadFile` and 8 per-file megabasterd entries (all with `###n={folderId}` suffix) — assert all 8 entries map to the single DownloadFile
- [x] 2.3 Add a test that Tier 1 still works after Tier 3 is added (single file URL match is unaffected)
- [x] 2.4 Run the full test suite and confirm all tests pass (`cd megaqueue && pytest`)
