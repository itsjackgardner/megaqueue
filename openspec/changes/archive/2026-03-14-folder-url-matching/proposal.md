## Why

When a user submits a mega.nz folder URL, megabasterd expands it into individual per-file downloads — each with a distinct URL containing a `###n={folderID}` suffix. The current worker has Tier 2 matching via a `sourceUrl` field that megabasterd does not actually return, so folder-split entries never match the stored `DownloadFile.url`, and the download is incorrectly marked as "Disappeared from megabasterd" after the grace period.

## What Changes

- Add **Tier 3 folder-ID matching** in `_match_megabasterd_files()`: extract the folder ID from `###n={folderID}` in each megabasterd URL and match it against the folder ID in `DownloadFile` records that use `mega.nz/folder/{id}` URLs.
- Add a helper `_extract_folder_id(url)` that returns the folder ID from either a `mega.nz/folder/{id}#key` URL or a `###n={folderID}` suffix.
- Remove or demote the dead Tier 2 `sourceUrl` path (megabasterd does not return this field).
- Update the `download-engine` spec to reflect actual matching behaviour (folder-ID-based, not sourceUrl-based).

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `download-engine`: URL matching requirement changes — replace sourceUrl-based matching with folder-ID matching extracted from `###n={folderID}` suffixes in megabasterd URLs.

## Impact

- `megaqueue/worker.py` — `_normalize_mega_url`, `_match_megabasterd_files`
- `megaqueue/tests/test_worker.py` — update/add tests for folder-ID matching
- `openspec/specs/download-engine/spec.md` — requirement update for URL matching
