## REMOVED Requirements

### Requirement: Organizer moves movie files to Plex movie folder structure
**Reason**: Replaced by FileBot-based organization (`filebot-integration` capability). FileBot handles routing, naming, and Plex folder structure natively.
**Migration**: See `filebot-integration` spec — FileBot `--format "{plex}"` with `--output <PLEX_MOVIES_DIR>` produces equivalent output.

### Requirement: Organizer moves TV files to Plex TV folder structure
**Reason**: Replaced by FileBot-based organization (`filebot-integration` capability).
**Migration**: See `filebot-integration` spec — FileBot `--format "{plex}"` with `--output <PLEX_TV_DIR>` produces equivalent output.

### Requirement: Organizer extracts multi-part archives before organizing
**Reason**: Replaced by `filebot -extract` in the `filebot-integration` capability.
**Migration**: FileBot handles `.rar`, `.zip`, `.7z`, `.001` extraction natively.

### Requirement: Organizer consolidates archive parts across folders before extraction
**Reason**: Replaced by `filebot -extract` accepting a file list directly.
**Migration**: FileBot handles multi-part archives when all parts are passed as arguments.

### Requirement: Organizer routes each TV episode file to the correct season folder independently
**Reason**: FileBot handles per-file season detection and routing via `{plex}` format string.
**Migration**: No action needed — FileBot behavior is equivalent.

### Requirement: Organizer discovers source files from DownloadFile paths
**Reason**: With the folder-expansion change (see `download-engine` and `data-model` specs), each file now has its own `DownloadFile` record with a `name` field. The worker constructs source paths from `MEGABASTERD_DOWNLOAD_DIR + DownloadFile.name` directly.
**Migration**: Worker resolves file paths from child DownloadFile records rather than walking directory trees.

## MODIFIED Requirements

### Requirement: Organizer cleans up temp directory after organizing
The system SHALL delete the temporary extraction directory after FileBot's rename step completes, whether or not it succeeded. The source files in `MEGABASTERD_DOWNLOAD_DIR` are removed by FileBot's `--action move` and do not require separate cleanup.

#### Scenario: Temp directory removed after successful organization
- **WHEN** FileBot successfully extracts and renames files
- **THEN** the temporary extraction directory is removed and the source files are gone (moved by FileBot)

#### Scenario: Temp directory removed after failure
- **WHEN** FileBot fails during extraction or rename
- **THEN** the temporary extraction directory is still removed and the error is propagated to mark the download as failed

### Requirement: Organizer updates download status on completion
The system SHALL set the download status to "complete" after successful file organization, and to "failed" with an error message if organization fails.

#### Scenario: Successful organization marks download complete
- **WHEN** FileBot moves all files to Plex folders successfully
- **THEN** the download status is set to "complete" and file_path is updated on each DownloadFile with the final destination path

#### Scenario: Organization failure marks download failed
- **WHEN** FileBot exits non-zero (e.g., file not found, permission error)
- **THEN** the download status is set to "failed" with a descriptive error_message containing FileBot's stderr

### Requirement: Organizer returns organized file paths for all placed files
The system SHALL return a list of all final destination paths for files that were organized, parsed from FileBot's stdout. The worker SHALL update each `DownloadFile.file_path` with the final destination path.

#### Scenario: Multi-episode download paths updated
- **WHEN** a TV download with 5 episodes is organized to various season folders by FileBot
- **THEN** the organizer returns 5 destination paths and the worker updates file records accordingly
