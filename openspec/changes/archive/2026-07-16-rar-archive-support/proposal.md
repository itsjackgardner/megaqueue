## Why

When a download contains an archive (e.g. `.rar`), the organiser extracts it via `rarfile` + `unrar` before routing files to Plex. On the NUC, extraction silently produces no files — `rarfile.RarFile.extractall()` completes without error but nothing appears in the temp directory. This causes `"Archive H2OBoy.rar produced no files"` even though the archive is valid and contains a movie file. The user's only option is to manually extract the archive outside the app, but clicking retry still tries to extract the original `.rar` — and if the user removed/renamed it after manual extraction, retry fails with `FileNotFoundError` instead.

## What Changes

- Fix `.rar` extraction to work reliably on Windows (diagnose and fix the `unrar`/`rarfile` configuration issue)
- Add a pre-extracted directory fallback: when an archive file is missing but a same-stem directory with extracted media files exists, skip extraction and organise the directory contents directly
- This enables a manual recovery flow: user extracts the archive themselves, clicks retry, and the system picks up the extracted content

## Capabilities

### New Capabilities

- `archive-recovery`: Resilient archive handling — detect pre-extracted content when the original archive is missing, and allow manual file placement for reprocessing

### Modified Capabilities

- `file-organizer`: Source path resolution gains fallback logic for missing archives with pre-extracted content

## Impact

- **Code**: `organiser.py` (fix extraction, accept pre-extracted directories), `lifecycle.py` (resolve_source_paths fallback)
- **Dependencies**: None new — `rarfile`, `zipfile`, `py7zr` already present. May need `unrar` binary configured correctly on the NUC.
- **Data model**: No schema changes required
- **Risk**: Low — fallback only triggers when the primary path fails, so existing happy-path behaviour is unchanged
