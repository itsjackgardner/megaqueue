## ADDED Requirements

### Requirement: Megabasterd API returns sourceUrl and path on each status entry
The megabasterd fork's `/status` endpoint SHALL include two additional fields on each download entry:
- `sourceUrl`: The original URL that was submitted to `/start` (preserves folder URL even after splitting into per-file entries)
- `path`: The relative path from the download directory (e.g., `FolderName/file.mkv` for folder contents, `file.mkv` for single files)

#### Scenario: Single file download status
- **WHEN** megabasterd downloads a single file URL `https://mega.nz/file/abc#xyz`
- **THEN** the status entry includes `sourceUrl: "https://mega.nz/file/abc#xyz"` and `path: "Movie.2024.1080p.mkv"`

#### Scenario: Folder URL split into per-file entries
- **WHEN** megabasterd receives folder URL `https://mega.nz/folder/abc#xyz` containing 3 files
- **THEN** the status response includes 3 entries, each with `sourceUrl: "https://mega.nz/folder/abc#xyz"` and `path` like `"FolderName/file1.mkv"`, `"FolderName/file2.mkv"`, etc.

### Requirement: Worker matches folder-split entries via sourceUrl
The worker SHALL use a two-tier matching strategy when correlating megabasterd status entries to `DownloadFile` records:
1. First match by normalized URL (existing behavior for single file downloads)
2. For unmatched entries, match by `sourceUrl` — if a megabasterd entry's `sourceUrl` matches a `DownloadFile`'s URL (after normalization), it belongs to that download file

#### Scenario: Single file matched by URL
- **WHEN** megabasterd reports an entry with URL matching a `DownloadFile`'s URL
- **THEN** the entry is matched to that `DownloadFile` via URL normalization

#### Scenario: Folder-split files matched by sourceUrl
- **WHEN** megabasterd splits a folder URL into 5 per-file entries with `sourceUrl` matching a `DownloadFile`'s URL
- **THEN** all 5 entries are matched to that single `DownloadFile`

#### Scenario: Folder-split progress aggregation
- **WHEN** a `DownloadFile` (folder URL) matches 3 megabasterd entries with varying progress
- **THEN** the worker aggregates `progress_bytes` and `total_bytes` across all matched entries, and the `DownloadFile` is only marked "finished" when all matched entries report `finished: true`

### Requirement: Worker resolves source file paths before post-processing
The system SHALL resolve source file paths using the `path` field from megabasterd status entries combined with the configured download directory. For folder-split downloads, the worker SHALL collect all `path` values from matched entries. The resolved paths SHALL be stored so the organizer can locate files on disk.

#### Scenario: Single file path resolved
- **WHEN** megabasterd reports a finished download with `path: "Movie.2024.1080p.mkv"`
- **THEN** the worker resolves the source path as `<MEGABASTERD_DOWNLOAD_DIR>/Movie.2024.1080p.mkv`

#### Scenario: Folder-split files paths resolved
- **WHEN** a folder download finishes and its 3 matched entries have `path` values `"Show.S01/ep01.mkv"`, `"Show.S01/ep02.mkv"`, `"Show.S01/ep03.mkv"`
- **THEN** the worker resolves 3 source paths under `<MEGABASTERD_DOWNLOAD_DIR>/`

#### Scenario: Path field is missing
- **WHEN** megabasterd reports a finished download without a `path` field
- **THEN** the worker marks the download as failed with error "Could not determine download file path from megabasterd"

### Requirement: Megabasterd download directory is configurable
The system SHALL read the megabasterd download directory from the `MEGAQUEUE_MEGABASTERD_DOWNLOAD_DIR` environment variable. This value is required and the application SHALL exit on startup if it is not set.

#### Scenario: Download dir configured
- **WHEN** `MEGAQUEUE_MEGABASTERD_DOWNLOAD_DIR` is set to `D:/MegaDownloads`
- **THEN** the worker resolves file paths under `D:/MegaDownloads/`

#### Scenario: Download dir not configured
- **WHEN** `MEGAQUEUE_MEGABASTERD_DOWNLOAD_DIR` is not set
- **THEN** the application exits with error "Required config MEGAQUEUE_MEGABASTERD_DOWNLOAD_DIR is not set"

## MODIFIED Requirements

### Requirement: Worker updates per-file progress from megabasterd status
The system SHALL match each megabasterd download entry to a DownloadFile record by normalized mega.nz URL (or by `sourceUrl` for folder-split entries) and update that file's progress_bytes, total_bytes, speed, name, and status. For folder-split downloads where one `DownloadFile` matches multiple megabasterd entries, progress SHALL be aggregated across all matched entries.

#### Scenario: File progress is updated
- **WHEN** megabasterd reports a file at 500MB of 1.2GB with speed 5MB/s
- **THEN** the matching DownloadFile's progress_bytes, total_bytes, and speed are updated

#### Scenario: File name is populated from megabasterd
- **WHEN** megabasterd reports a download with name "Movie.2024.1080p.mkv"
- **THEN** the matching DownloadFile's name field is set to that value

#### Scenario: Folder-split progress is aggregated
- **WHEN** a folder URL DownloadFile matches 3 megabasterd entries: (200MB/400MB), (100MB/300MB), (300MB/500MB)
- **THEN** the DownloadFile's progress_bytes is set to 600MB and total_bytes to 1200MB

### Requirement: Worker detects file completion and triggers post-processing
The system SHALL detect that all files in a download have finished by checking `finished: true` on each matched megabasterd entry. For folder-split downloads, a `DownloadFile` is only considered finished when ALL of its matched megabasterd entries report `finished: true`. When all files are finished, the worker SHALL resolve source file paths, then transition the download to "processing" and trigger post-processing.

#### Scenario: All files complete
- **WHEN** megabasterd reports `finished: true` for all files in a download
- **THEN** the worker resolves source paths, transitions to "processing", and begins file organization

#### Scenario: Folder-split download partially complete
- **WHEN** a folder URL matches 3 megabasterd entries but only 2 report `finished: true`
- **THEN** the DownloadFile status remains "downloading" and post-processing is not triggered

#### Scenario: Finished downloads are cleared from megabasterd
- **WHEN** post-processing completes for a download
- **THEN** the worker calls `POST /stop` for each file's URL to remove them from megabasterd
