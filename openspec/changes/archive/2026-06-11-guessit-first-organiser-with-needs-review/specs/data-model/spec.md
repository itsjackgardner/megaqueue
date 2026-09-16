## MODIFIED Requirements

### Requirement: Download entity stores queue metadata
The system SHALL persist a Download entity with fields: id (primary key), title (nullable string — populated by the metadata-resolution capability after megabasterd reports filenames), year (optional integer), media_type (nullable enum: movie | tv), status (enum: queued | downloading | needs_review | processing | complete | failed | cancelled), downloading_since (optional timestamp), error_message (optional string), metadata_confidence (enum: high | low, default low), metadata_source (nullable enum: guessit | user), created_at (timestamp), and updated_at (timestamp).

#### Scenario: New download is created without user-provided metadata
- **WHEN** a download is created from one or more mega.nz links only
- **THEN** the entity is persisted with `title=null`, `year=null`, `media_type=null`, `status="queued"`, `metadata_confidence="low"`, `metadata_source=null`, one DownloadFile per link, and auto-generated timestamps

#### Scenario: Download status transitions are recorded
- **WHEN** a download's status changes from "queued" to "downloading"
- **THEN** the updated_at timestamp SHALL be updated to the current time

#### Scenario: needs_review status blocks processing
- **WHEN** all of a Download's leaf files finish but `metadata_confidence` is `low`
- **THEN** the Download transitions to `needs_review` (not `processing`), and the file organiser SHALL NOT run until the status moves to `processing`

### Requirement: DownloadFile entity tracks individual file state
The system SHALL persist a DownloadFile entity with fields: id (primary key), download_id (foreign key to Download), parent_id (optional foreign key to DownloadFile, for folder-split child records), url (mega.nz URL), name (optional string, populated from megabasterd), status (enum: queued | downloading | finished | failed), progress_bytes (integer), total_bytes (integer), speed (integer, bytes/sec), error_message (optional string), file_path (optional string, final organized path), and is_extra (boolean, default false — set by the metadata-resolution capability when the file is a movie featurette/trailer rather than the main feature).

For folder URL submissions, one "parent" DownloadFile record is created with the folder URL. When megabasterd splits the folder into individual files, child DownloadFile records are created with `parent_id` pointing to the parent record. Child records track per-file progress independently. The `is_extra` flag is only meaningful on leaf records of movie-typed Downloads.

#### Scenario: Multi-link download creates multiple DownloadFile records
- **WHEN** a download is created with links ["https://mega.nz/file/a", "https://mega.nz/file/b", "https://mega.nz/file/c"]
- **THEN** three DownloadFile records are created, each with status "queued", null parent_id, `is_extra=false`, and linked to the parent Download

#### Scenario: Individual file progress is tracked
- **WHEN** megabasterd reports one file at 500MB/1.2GB and another at 200MB/800MB
- **THEN** each DownloadFile record reflects its own progress_bytes and total_bytes independently

#### Scenario: Folder URL creates parent and child records
- **WHEN** a download is created with a folder URL "https://mega.nz/folder/abc#key" and megabasterd splits it into 3 files
- **THEN** the original DownloadFile (folder URL) acts as the parent and 3 child DownloadFile records are created with parent_id referencing it

#### Scenario: Child records cascade on parent delete
- **WHEN** a parent DownloadFile (folder record) is deleted
- **THEN** all child DownloadFile records with that parent_id are also deleted

#### Scenario: is_extra flag tags movie featurettes
- **WHEN** a movie Download has a main feature and four featurette files, and metadata resolution has run
- **THEN** the four featurette leaf records have `is_extra=true` and the main feature has `is_extra=false`

### Requirement: Download status is derived from file statuses
The system SHALL derive the Download's overall status from its files and metadata confidence: all files finished AND `metadata_confidence="high"` → "processing"; all files finished AND `metadata_confidence="low"` → "needs_review"; all files failed → "failed"; any file downloading or finished → "downloading"; otherwise → "queued". Once a download is in `needs_review`, the worker SHALL NOT change its status back to `downloading` or `processing` automatically — only an explicit transition driven by the resolve route SHALL move it to `processing`.

#### Scenario: All files complete with high confidence triggers processing
- **WHEN** a download has 3 files, all transition to "finished", and `metadata_confidence="high"`
- **THEN** the download's status becomes "processing" and post-processing is triggered

#### Scenario: All files complete with low confidence triggers needs_review
- **WHEN** a download has 3 files, all transition to "finished", and `metadata_confidence="low"`
- **THEN** the download's status becomes "needs_review" and post-processing is NOT triggered

#### Scenario: Partial failure keeps download active
- **WHEN** a download has 3 files, 1 has finished, 1 is downloading, and 1 has failed
- **THEN** the download's status remains "downloading"

#### Scenario: needs_review is not auto-cleared
- **WHEN** a download is in `needs_review` and the worker polls
- **THEN** the worker does not change the status; the user must submit the resolve form to move it to `processing`

## ADDED Requirements

### Requirement: Database migration adds metadata-resolution columns
The system SHALL add `metadata_confidence`, `metadata_source` to the `downloads` table and `is_extra` to the `download_files` table when starting against an existing database. Existing rows SHALL default to `metadata_confidence="high"` (so they bypass the new review gate), `metadata_source=null`, and `is_extra=false`. Migrations SHALL be defined as named, ordered functions in a dedicated `migrations.py` module rather than inline in `init_db()`, so future schema changes have a single registration point.

#### Scenario: Existing database migrates safely
- **WHEN** the application starts against a database without the new columns
- **THEN** `migrations.py` runs the registered migration functions in order, each adding its columns with the defaults above, and existing in-flight downloads continue through the legacy code path

#### Scenario: Migrations are idempotent across restarts
- **WHEN** the application restarts against a database where the new columns already exist
- **THEN** the migrations re-run safely (each `ALTER TABLE` is caught as already-applied) and no data is altered
