## MODIFIED Requirements

### Requirement: Worker updates per-file progress from megabasterd status
The system SHALL match each megabasterd download entry to a DownloadFile record by normalized mega.nz URL (or by folder ID for folder-split entries) and update that file's progress_bytes, total_bytes, speed, name, and status.

For folder-split downloads, the worker SHALL first check whether child DownloadFile records exist for the parent folder DownloadFile. If children do not yet exist, the worker SHALL create them (one per megabasterd entry) with parent_id set to the folder DownloadFile. Each child record SHALL then be updated independently from its matched megabasterd entry. The parent folder DownloadFile is no longer directly updated from megabasterd after expansion.

#### Scenario: File progress is updated
- **WHEN** megabasterd reports a file at 500MB of 1.2GB with speed 5MB/s
- **THEN** the matching DownloadFile's progress_bytes, total_bytes, and speed are updated

#### Scenario: File name is populated from megabasterd
- **WHEN** megabasterd reports a download with name "Movie.2024.1080p.mkv"
- **THEN** the matching DownloadFile's name field is set to that value

#### Scenario: Folder-split creates child DownloadFile records on first tick
- **WHEN** megabasterd splits a folder URL into 3 file entries and no child DownloadFile records exist yet
- **THEN** the worker creates 3 child DownloadFile records linked to the folder DownloadFile via parent_id, each initialized with the megabasterd entry's URL, name, and progress data

#### Scenario: Folder-split expansion is idempotent
- **WHEN** megabasterd splits a folder URL into 3 file entries and child records already exist from a previous tick
- **THEN** the worker updates the existing child records and does not create duplicates

### Requirement: Worker detects file completion and triggers post-processing
The system SHALL detect that all files in a download have finished. For folder-split downloads, completion is determined by checking that all child DownloadFile records have status "finished". When all files are finished, the worker SHALL collect source file paths from `DownloadFile.name` combined with `MEGABASTERD_DOWNLOAD_DIR`, transition the download to "processing", and trigger post-processing.

#### Scenario: All files complete
- **WHEN** megabasterd reports `finished: true` for all files in a download
- **THEN** the worker collects source paths, transitions to "processing", and begins file organization

#### Scenario: Folder-split download partially complete
- **WHEN** a folder URL has 3 child DownloadFile records but only 2 have status "finished"
- **THEN** post-processing is not triggered

#### Scenario: Finished downloads are cleared from megabasterd
- **WHEN** post-processing completes for a download
- **THEN** the worker calls `POST /stop` for each file's URL to remove them from megabasterd

### Requirement: Worker resolves source file paths before post-processing
The system SHALL resolve source file paths by combining `MEGABASTERD_DOWNLOAD_DIR` with the `name` field from each leaf DownloadFile record (child records for folder downloads, direct records for single-file downloads). The resolved paths are passed to the FileBot organizer.

#### Scenario: Single file path resolved
- **WHEN** a download completes with a DownloadFile whose name is "Movie.2024.1080p.mkv"
- **THEN** the worker resolves the source path as `<MEGABASTERD_DOWNLOAD_DIR>/Movie.2024.1080p.mkv`

#### Scenario: Folder-split file paths resolved from children
- **WHEN** a folder download finishes with 3 child DownloadFile records with names "ep01.mkv", "ep02.mkv", "ep03.mkv"
- **THEN** the worker resolves 3 source paths under `<MEGABASTERD_DOWNLOAD_DIR>/`

#### Scenario: Name field is missing
- **WHEN** a DownloadFile has no name set at post-processing time
- **THEN** the worker marks the download as failed with error "Could not determine download file path: DownloadFile name not set"
