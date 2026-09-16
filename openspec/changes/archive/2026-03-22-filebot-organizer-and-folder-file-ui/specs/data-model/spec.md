## MODIFIED Requirements

### Requirement: DownloadFile entity tracks individual file state
The system SHALL persist a DownloadFile entity with fields: id (primary key), download_id (foreign key to Download), parent_id (optional foreign key to DownloadFile, for folder-split child records), url (mega.nz URL), name (optional string, populated from megabasterd), status (enum: queued | downloading | finished | failed), progress_bytes (integer), total_bytes (integer), speed (integer, bytes/sec), error_message (optional string), and file_path (optional string, final organized path).

For folder URL submissions, one "parent" DownloadFile record is created with the folder URL. When megabasterd splits the folder into individual files, child DownloadFile records are created with `parent_id` pointing to the parent record. Child records track per-file progress independently.

#### Scenario: Multi-link download creates multiple DownloadFile records
- **WHEN** a download is created with links ["https://mega.nz/file/a", "https://mega.nz/file/b", "https://mega.nz/file/c"]
- **THEN** three DownloadFile records are created, each with status "queued", null parent_id, and linked to the parent Download

#### Scenario: Individual file progress is tracked
- **WHEN** megabasterd reports one file at 500MB/1.2GB and another at 200MB/800MB
- **THEN** each DownloadFile record reflects its own progress_bytes and total_bytes independently

#### Scenario: Folder URL creates parent and child records
- **WHEN** a download is created with a folder URL "https://mega.nz/folder/abc#key" and megabasterd splits it into 3 files
- **THEN** the original DownloadFile (folder URL) acts as the parent and 3 child DownloadFile records are created with parent_id referencing it

#### Scenario: Child records cascade on parent delete
- **WHEN** a parent DownloadFile (folder record) is deleted
- **THEN** all child DownloadFile records with that parent_id are also deleted
