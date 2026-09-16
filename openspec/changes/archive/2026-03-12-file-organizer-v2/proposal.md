## Why

The current file organizer has a fundamental gap: it doesn't know where megabasterd actually put the downloaded files. The `organize_download` function tries to derive a path from `config.MEGABASTERD_API_URL` (which doesn't work) and falls back to whatever `file_paths` happen to be set on the download — which are never populated. Additionally, the organizer treats each download as a flat list of files, with no understanding of mega.nz folder downloads, multi-episode folders, or split archives spread across multiple folders. This makes it unable to handle the real-world download patterns users encounter.

## What Changes

- **Extend megabasterd's `/status` API** (in our fork) to include `sourceUrl` (the original URL submitted to `/start`) and `path` (relative path from download dir, e.g., `FolderName/file.mkv`). This is needed because megabasterd splits folder URLs into individual per-file entries with their own URLs, breaking URL-based matching
- **Use megabasterd's new `path` field** to determine the actual disk location for each download entry, and use the configured megabasterd download path to locate files on disk
- **Detect and handle folder downloads** — a single mega.nz URL can be a folder containing multiple episode files or archive parts; megabasterd splits these into per-file entries but downloads them into the folder on disk
- **Support multi-episode TV downloads** — when a folder contains multiple episode files (e.g., S01E01, S01E02, ...), route each episode to the correct `Season XX/` subfolder independently
- **Handle split archives across folders** — when multiple URLs each download a folder containing parts of a split archive, consolidate and extract them before organizing
- **Add a megabasterd download path config value** so the organizer knows the root directory where megabasterd saves files
- **Populate `DownloadFile.file_path`** with the actual source path from megabasterd's download directory after download completes, before organization begins
- **Match folder-split downloads via `sourceUrl`** — when megabasterd splits a folder URL into per-file entries, use the new `sourceUrl` field to match them back to the original `DownloadFile` record

## Capabilities

### New Capabilities

_(none — all changes enhance the existing file-organizer capability)_

### Modified Capabilities

- `file-organizer`: Requirements change to support folder-aware file discovery, multi-episode routing, cross-folder archive consolidation, and megabasterd download path resolution
- `download-engine`: Worker must match folder-split entries via `sourceUrl`, populate `DownloadFile.file_path` from megabasterd's `path` field + download directory, and handle one-to-many URL expansion for folder downloads
- `web-ui`: Download detail view shows where each file was moved to after organization

## Impact

- **`organizer.py`**: Major rewrite — new file discovery logic, folder handling, multi-episode routing, archive consolidation
- **`worker.py`**: `_post_process` must resolve source file paths from megabasterd name + download dir before calling organizer
- **`config.py`**: New `MEGABASTERD_DOWNLOAD_DIR` required config value
- **`models.py`**: No schema changes needed — existing `DownloadFile.name` and `file_path` fields are sufficient
- **megabasterd (fork)**: API change to `/status` — add `sourceUrl` and `path` fields to each download entry
- **Dependencies**: No new Python dependencies required
