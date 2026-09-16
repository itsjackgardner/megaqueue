## ADDED Requirements

### Requirement: Download detail view shows file destination paths
The download detail view SHALL display the final destination path for each file after organization is complete. This allows the user to verify where files were placed.

#### Scenario: Completed download shows file destinations
- **WHEN** a user views a completed download that organized 3 files to Plex directories
- **THEN** each file entry shows its final destination path (e.g., `D:/Plex/TV Shows/Breaking Bad/Season 03/Breaking.Bad.S03E05.mkv`)

#### Scenario: In-progress download does not show destinations
- **WHEN** a user views a download that is still downloading
- **THEN** file entries do not show destination paths (file_path is not yet set to a destination)
