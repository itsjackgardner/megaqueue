## MODIFIED Requirements

### Requirement: Download entity stores queue metadata
The system SHALL persist a Download entity with fields: id (primary key), title (nullable string — populated by the metadata-resolution capability after megabasterd reports filenames), year (optional integer), media_type (nullable enum: movie | tv), status (enum: queued | downloading | needs_review | processing | complete | failed | cancelled), downloading_since (optional timestamp), error_message (optional string), metadata_confidence (enum: high | low, default low), metadata_source (nullable enum: guessit | user), ongoing (boolean, default false), created_at (timestamp), and updated_at (timestamp).

#### Scenario: New download is created without user-provided metadata
- **WHEN** a download is created from one or more mega.nz links only
- **THEN** the entity is persisted with `title=null`, `year=null`, `media_type=null`, `status="queued"`, `metadata_confidence="low"`, `metadata_source=null`, `ongoing=false`, one DownloadFile per link, and auto-generated timestamps

#### Scenario: Download status transitions are recorded
- **WHEN** a download's status changes from "queued" to "downloading"
- **THEN** the updated_at timestamp SHALL be updated to the current time

#### Scenario: needs_review status blocks processing
- **WHEN** all of a Download's leaf files finish but `metadata_confidence` is `low`
- **THEN** the Download transitions to `needs_review` (not `processing`), and the file organiser SHALL NOT run until the status moves to `processing`

#### Scenario: Ongoing flag defaults to false
- **WHEN** a new Download is created
- **THEN** `ongoing` is `false` by default

## ADDED Requirements

### Requirement: Database migration adds ongoing column
The system SHALL add a `ongoing` boolean column (default `false`) to the `downloads` table via a new named migration in `migrations.py`. Existing rows SHALL default to `ongoing=false`. The migration SHALL be idempotent.

#### Scenario: Existing database migrates safely
- **WHEN** the application starts against a database without the `ongoing` column
- **THEN** the migration adds `ongoing` with default `false` and existing downloads are unaffected

#### Scenario: Migration is idempotent
- **WHEN** the application restarts against a database that already has the `ongoing` column
- **THEN** the migration runs safely without error
