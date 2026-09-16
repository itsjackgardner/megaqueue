## MODIFIED Requirements

### Requirement: Organizer cleans up temp directory after organizing
The system SHALL delete the temporary extraction directory after the rename step completes, whether or not it succeeded. Source files in `MEGABASTERD_DOWNLOAD_DIR` SHALL be removed by the organiser's move step and do not require separate cleanup. When organising from a pre-extracted directory, the system SHALL NOT delete the source directory — only move files out of it. If the directory becomes empty after all files are moved, it MAY be removed.

#### Scenario: Temp directory removed after successful organization
- **WHEN** the organiser successfully extracts archives and moves files to Plex
- **THEN** the temporary extraction directory is removed and the source files are gone (moved)

#### Scenario: Temp directory removed after failure
- **WHEN** the organiser fails during extraction or move
- **THEN** the temporary extraction directory is still removed and the error is propagated to mark the download as failed

#### Scenario: Pre-extracted directory preserved on partial success
- **WHEN** the organiser moves some files from a pre-extracted directory but fails on others
- **THEN** the pre-extracted directory is NOT deleted and unmoved files remain in place for manual recovery
