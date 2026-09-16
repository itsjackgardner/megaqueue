## Context

When all files in a download reach FINISHED, `lifecycle.derive_download_status()` transitions the download to PROCESSING, which triggers `post_process()`. This calls `resolve_source_paths()` to build file paths, then `organiser.organize_download()` handles extraction and routing.

The organiser already handles archives — it checks `_is_archive()`, extracts via `rarfile`/`zipfile`/`py7zr` into a temp directory, then routes extracted content to Plex. However, on the NUC, `.rar` extraction silently fails: `rarfile.RarFile.extractall()` completes without raising an exception, but no files appear in the temp directory. The organiser then raises `"Archive H2OBoy.rar produced no files"`.

Real failure case: The Waterboy (1998) downloaded as `H2OBoy.rar` (2.1 GB). The archive was found and `extractall()` ran, but `temp_dir.rglob("*")` found nothing. The user manually extracted it and clicked retry, but the system tried to extract the original `.rar` again (or couldn't find it if the user had moved it). Two distinct problems:
1. **Primary**: `rarfile` extraction silently produces no files (likely `unrar` binary misconfiguration on Windows)
2. **Secondary**: No recovery path when the user has already extracted the archive manually

## Goals / Non-Goals

**Goals:**
- Fix `.rar` extraction so it works reliably on Windows (diagnose `unrar`/`rarfile` configuration)
- Add better diagnostics when extraction produces no files (log what `unrar` tool is being used, whether it's on PATH)
- When an archive source file is missing, detect pre-extracted content and organise it directly
- Make the retry flow work after a user has manually extracted an archive

**Non-Goals:**
- Supporting arbitrary user-placed files unrelated to the original download
- UI for browsing/selecting extracted files — the system should detect them automatically
- Changing how megabasterd downloads or names files

## Decisions

### 1. Fix `rarfile` extraction with explicit `unrar` tool validation

Before extracting, verify that `rarfile.UNRAR_TOOL` points to a working `unrar` binary. Add a startup check or pre-extraction validation that runs `unrar --version` (or equivalent) and raises a clear error if it's missing or broken. After `extractall()`, verify the temp directory is non-empty before proceeding — if empty, raise with diagnostic info (which tool was used, the archive path, the temp dir path) rather than the generic "produced no files."

**Why:** `rarfile` delegates decompression to a system binary (`unrar` or `unrar.exe`). If the binary isn't on PATH, some `rarfile` versions silently do nothing instead of raising. Validating upfront and adding post-extraction assertions catches this reliably.

### 2. Fallback directory detection in `resolve_source_paths()`

When a source file doesn't exist and its name matches an archive extension, look for a directory with the same stem (e.g. `H2OBoy.rar` → `H2OBoy/`) in `MEGABASTERD_DOWNLOAD_DIR`. If found, treat it as pre-extracted content.

**Why over alternatives:**
- *Adding a "re-upload" form*: Too much ceremony for a simple recovery case. The user already has the files on disk.
- *Storing extraction state in the DB*: Over-engineered. The filesystem is the source of truth — if the directory exists, the content is there.

### 3. New `_resolve_pre_extracted()` helper in organiser

When `organize_download()` receives a directory path instead of a file, it skips extraction and treats the directory contents as already-extracted files. The existing routing logic (`_route()` and `_move()`) handles each file the same way.

**Why:** This reuses 100% of the existing routing/moving code. The only branch is "extract archive to temp dir" vs "use existing directory as-is."

### 4. Source path resolution returns `(path, is_pre_extracted)` tuples

`resolve_source_paths()` returns metadata about whether each path is a pre-extracted directory so the organiser knows to skip extraction without re-checking the filesystem.

**Why over just checking `path.is_dir()` in organiser:** Keeps the detection logic in one place (lifecycle) rather than splitting it between lifecycle and organiser.

## Risks / Trade-offs

- **[Ambiguous directory match]** → A directory named `H2OBoy/` could exist for reasons unrelated to the archive. Mitigation: Only fall back to directory match when the original file was an archive extension AND the directory contains media files (video/subtitle extensions).
- **[Partial extraction]** → User may have partially extracted the archive. Mitigation: The organiser already handles individual file failures — if some files are missing or corrupt, those DownloadFiles get marked failed while others succeed.
- **[Temp directory from prior failed run]** → A leftover temp directory from a previous extraction attempt could be mistaken for user-extracted content. Mitigation: The organiser's temp directories use `tempfile.mkdtemp()` with a unique prefix, not the archive stem name, so they won't match.
