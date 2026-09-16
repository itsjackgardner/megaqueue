## Context

The file organizer (`organizer.py`) currently receives a `Download` object and expects `download.file_paths` to contain valid source paths. In practice, these paths are never populated — the worker doesn't resolve where megabasterd saved files to disk. The organizer also treats downloads as flat file lists, with no awareness of folder downloads or multi-file structures common on mega.nz.

Megabasterd's `/status` API returns a `name` field for each download entry. However, when a folder URL is submitted, megabasterd splits it into individual per-file download entries with their own mega.nz URLs. This means: (a) the URLs in the status response don't match the original folder URL stored in `DownloadFile`, and (b) the `name` field is just the bare filename, not the folder-relative path. The files are still downloaded into the folder on disk, but we can't derive the path from `name` alone. Since we maintain a fork of megabasterd, we can extend the API to solve both problems.

## Goals / Non-Goals

**Goals:**
- Resolve actual file locations from megabasterd's `name` field + download directory
- Handle all five download patterns: single file, single folder with episodes, single folder with archive parts, multiple single files, multiple folders
- Route each media file to the correct Plex folder independently (per-file season detection for TV)
- Consolidate archive parts that may be spread across multiple folders before extraction

**Non-Goals:**
- Automatic media type detection (user still specifies movie vs. tv at download creation)
- Renaming files (files keep their original names)
- Handling nested folder structures beyond one level deep
- Transcoding or media format validation

## Decisions

### 1. Extend megabasterd `/status` API with `sourceUrl` and `path`

**Decision**: Add two fields to each download entry in megabasterd's `/status` response:
- `sourceUrl`: The original URL that was submitted to `/start` (preserves the folder URL even after splitting)
- `path`: The relative path from the download directory (e.g., `FolderName/file.mkv` for folder contents, `file.mkv` for single files)

**Rationale**: When megabasterd splits a folder URL into per-file entries, the per-file URLs don't match the original folder URL stored in `DownloadFile`. `sourceUrl` lets us match back. The `name` field alone is just the bare filename; `path` gives the full relative path needed to locate files on disk.

**Alternative considered**: Matching by filename/name only — rejected because filenames aren't unique across downloads. Also considered passing a `dest` parameter per download to namespace files — rejected as more complex and changes submission flow.

### 2. File discovery via megabasterd path + download dir

**Decision**: Before post-processing, the worker resolves each file's source path as `<MEGABASTERD_DOWNLOAD_DIR>/<path>` using the `path` field from megabasterd's status. For folder downloads that split into multiple entries, the worker collects all entries matching the `DownloadFile`'s URL via `sourceUrl` and resolves each one's path.

**Rationale**: The `path` field gives us the exact relative path from the download directory, handling both single files and folder contents correctly.

### 3. Two-phase organize: discover then route

**Decision**: Split organization into two phases:
1. **Discovery phase**: Walk all source paths from the download, collect every file, detect and extract archives, producing a flat list of media files to organize
2. **Routing phase**: Route each media file to its Plex destination based on media_type and filename analysis

**Rationale**: Decoupling discovery from routing lets us handle all download patterns uniformly. Whether files come from one folder, five folders, or extracted archives, the routing phase sees the same thing: a list of files to place.

### 4. Archive consolidation before extraction

**Decision**: When archive parts (`.rar`, `.001`, `.7z`, etc.) are found across multiple source directories, copy them into a single temp directory before extraction.

**Rationale**: Archive tools expect all parts in the same directory. Split archives spread across mega.nz folders need consolidation first. We copy rather than move so we can clean up predictably.

### 5. Per-file routing for TV episodes

**Decision**: Each file in a TV download is routed independently based on its filename. Season detection via `SxxExx` pattern determines the `Season XX/` subfolder. Files without season info go to the show root.

**Rationale**: A single download may contain episodes from multiple seasons (e.g., a "complete series" folder). Routing per-file ensures each episode lands in the right season folder.

### 6. Folder-split download matching via sourceUrl

**Decision**: When the worker polls megabasterd status, it matches entries to `DownloadFile` records using a two-tier strategy:
1. First, try matching by normalized URL (existing behavior, works for single file downloads)
2. For unmatched megabasterd entries, match by `sourceUrl` — if a megabasterd entry's `sourceUrl` matches a `DownloadFile`'s URL, it's a split file from that folder download

When a single `DownloadFile` (folder URL) matches multiple megabasterd entries, the worker treats all of them as belonging to that download file. Progress is aggregated. The download is only "finished" when all split entries report `finished: true`.

**Rationale**: This is backwards-compatible — single file downloads still match by URL. Folder downloads get matched by `sourceUrl`. No data model changes needed.

### 7. Source cleanup after successful organization

**Decision**: After all files are successfully moved to Plex directories, delete the source directory/files from the megabasterd download dir. If any file fails to move, abort cleanup and mark the download as failed.

**Rationale**: All-or-nothing cleanup prevents partial states where some files are organized and source files are already deleted.

## Risks / Trade-offs

- **[Risk] megabasterd `path` doesn't match disk** — If megabasterd reports a path that doesn't exist on disk (race condition, manual deletion), the organizer will fail with `FileNotFoundError`. → Mitigation: Clear error message in the download's `error_message` field; user can retry.

- **[Risk] Folder-split entries finish at different times** — Individual files from a folder download may finish before others, but we can't organize until all are done. → Mitigation: The worker already aggregates status per-Download; folder-split entries are aggregated under the same DownloadFile and the download only transitions to "processing" when all entries report finished.

- **[Risk] Archive parts in separate folders have naming conflicts** — Two folders could contain files with the same name that aren't related. → Mitigation: Only consolidate files matching archive extensions; non-archive files are routed individually per source folder.

- **[Risk] Very large folder downloads** — A folder with hundreds of files could be slow to walk and organize. → Mitigation: Acceptable for v2; the organizer runs in a background thread and doesn't block the web UI.

- **[Trade-off] No nested folder support** — We only look one level deep inside a downloaded folder. Deeply nested structures would need recursive handling. → Acceptable for now; mega.nz folder downloads are typically flat.
