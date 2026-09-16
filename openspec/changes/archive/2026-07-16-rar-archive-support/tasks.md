## 1. Fix rar extraction

- [x] 1.1 Diagnose `unrar` availability on the NUC: check if `unrar` is on PATH, check what `rarfile.UNRAR_TOOL` resolves to
- [x] 1.2 Add `_check_unrar()` helper in `organiser.py` that verifies the unrar binary is available before extraction; raise a clear error if not
- [x] 1.3 Add post-extraction validation in `_extract_archive()`: after `extractall()`, verify temp dir is non-empty; raise with diagnostic info (archive path, temp dir, configured tool) if empty

## 2. Media extension constants

- [x] 2.1 Add `MEDIA_EXTENSIONS` set to `organiser.py` (`.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.srt`, `.sub`, `.idx`, `.ass`, `.ssa`)
- [x] 2.2 Add `_has_media_files(directory)` helper that returns True if any file in the directory has a media extension

## 3. Source path resolution fallback

- [x] 3.1 Update `resolve_source_paths()` in `lifecycle.py` to detect missing archive files and look for a same-stem directory in `MEGABASTERD_DOWNLOAD_DIR`
- [x] 3.2 Validate the fallback directory contains media files using `_has_media_files()`; raise descriptive error if not
- [x] 3.3 Return source path metadata indicating whether each path is a pre-extracted directory (tuple of `(path, pre_extracted)`)

## 4. Organiser pre-extracted directory support

- [x] 4.1 Update `organize_download()` in `organiser.py` to accept pre-extracted flag per source path
- [x] 4.2 When a source is pre-extracted, skip extraction and use directory contents directly (list media files, route each through `_route()` / `_move()`)
- [x] 4.3 For pre-extracted directories, do NOT delete the source directory — only move files out; remove directory if empty after moves

## 5. Lifecycle integration

- [x] 5.1 Update `post_process()` in `lifecycle.py` to pass pre-extracted metadata through to `organize_download()`
- [x] 5.2 Add logging for fallback detection: log when a pre-extracted directory is used instead of the original archive

## 6. Tests

- [x] 6.1 Test `_check_unrar()` and post-extraction validation (unrar missing, extractall produces no files, extractall succeeds)
- [x] 6.2 Test `_has_media_files()` with video files, subtitle-only, and non-media-only directories
- [x] 6.3 Test `resolve_source_paths()` fallback: missing archive with valid directory, missing archive with no directory, missing archive with empty directory, missing non-archive file (no fallback)
- [x] 6.4 Test `organize_download()` with pre-extracted directory: movie routing, TV routing, cleanup behaviour
- [x] 6.5 Test full `post_process()` flow with pre-extracted fallback end-to-end
