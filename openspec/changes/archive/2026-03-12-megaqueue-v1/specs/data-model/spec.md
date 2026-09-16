## ADDED Requirements

### Requirement: Download entity stores queue metadata
The system SHALL persist a Download entity with fields: id (primary key), title (string), year (optional integer), media_type (enum: movie | tv), status (enum: queued | downloading | processing | complete | failed | cancelled), downloading_since (optional timestamp), error_message (optional string), created_at (timestamp), and updated_at (timestamp).

#### Scenario: New download is created with required fields
- **WHEN** a download is created with title "The Matrix", year 1999, media_type "movie", and one mega.nz link
- **THEN** the entity is persisted with status "queued", null error_message, one associated DownloadFile record, and auto-generated id, created_at, and updated_at timestamps

#### Scenario: Download status transitions are recorded
- **WHEN** a download's status changes from "queued" to "downloading"
- **THEN** the updated_at timestamp SHALL be updated to the current time

### Requirement: DownloadFile entity tracks individual file state
The system SHALL persist a DownloadFile entity with fields: id (primary key), download_id (foreign key to Download), url (mega.nz URL), name (optional string, populated from megabasterd), status (enum: queued | downloading | finished | failed), progress_bytes (integer), total_bytes (integer), speed (integer, bytes/sec), error_message (optional string), and file_path (optional string, final organized path).

#### Scenario: Multi-link download creates multiple DownloadFile records
- **WHEN** a download is created with links ["https://mega.nz/file/a", "https://mega.nz/file/b", "https://mega.nz/file/c"]
- **THEN** three DownloadFile records are created, each with status "queued" and linked to the parent Download

#### Scenario: Individual file progress is tracked
- **WHEN** megabasterd reports one file at 500MB/1.2GB and another at 200MB/800MB
- **THEN** each DownloadFile record reflects its own progress_bytes and total_bytes independently

### Requirement: Download aggregates progress from files
The system SHALL compute Download-level progress_bytes, total_bytes, speed, and file_paths as aggregates of its associated DownloadFile records.

#### Scenario: Aggregate progress across files
- **WHEN** a download has 2 files: one at 500MB/1GB and another at 200MB/500MB
- **THEN** the download's aggregate progress_bytes is 700MB, total_bytes is 1.5GB, and percentage is 46.7%

### Requirement: Download status is derived from file statuses
The system SHALL derive the Download's overall status from its files: all files finished → "processing", all files failed → "failed", any file downloading or finished → "downloading", otherwise → "queued".

#### Scenario: All files complete triggers processing
- **WHEN** a download has 3 files and all transition to "finished"
- **THEN** the download's status becomes "processing" and post-processing is triggered

#### Scenario: Partial failure keeps download active
- **WHEN** a download has 3 files, 1 has finished, 1 is downloading, and 1 has failed
- **THEN** the download's status remains "downloading"

### Requirement: DownloadFile records cascade on delete
The system SHALL delete all associated DownloadFile records when a Download is deleted (cascade delete).

#### Scenario: Deleting a download removes its files
- **WHEN** a download with 3 DownloadFile records is deleted
- **THEN** all 3 DownloadFile records are also removed from the database

### Requirement: Database uses SQLite with WAL mode
The system SHALL use SQLite as the database engine with WAL (Write-Ahead Logging) mode enabled for safe concurrent access from the web server thread and background worker thread.

#### Scenario: Concurrent read and write
- **WHEN** the worker thread updates file progress while the web thread reads the download list
- **THEN** both operations SHALL complete without database lock errors
