## ADDED Requirements

### Requirement: Organizer moves movie files to Plex movie folder structure
The system SHALL move completed movie downloads to `<PLEX_MOVIES_DIR>/<Title> (<Year>)/<filename>`.

#### Scenario: Movie with year is organized
- **WHEN** a download with title "Inception", year 2010, media_type "movie" completes with file "Inception.2010.1080p.mkv"
- **THEN** the file is moved to `<PLEX_MOVIES_DIR>/Inception (2010)/Inception.2010.1080p.mkv`

#### Scenario: Movie without year is organized
- **WHEN** a download with title "Inception", no year, media_type "movie" completes
- **THEN** the file is moved to `<PLEX_MOVIES_DIR>/Inception/<filename>`

### Requirement: Organizer moves TV files to Plex TV folder structure
The system SHALL move completed TV downloads to `<PLEX_TV_DIR>/<Title>/Season XX/<filename>`. If season cannot be determined from the filename, files are placed directly under `<Title>/`.

#### Scenario: TV episode is organized with season detection
- **WHEN** a download with title "Breaking Bad", media_type "tv" completes with file "Breaking.Bad.S03E05.mkv"
- **THEN** the file is moved to `<PLEX_TV_DIR>/Breaking Bad/Season 03/Breaking.Bad.S03E05.mkv`

#### Scenario: TV file without season info
- **WHEN** a download with title "Breaking Bad", media_type "tv" completes with file "breaking_bad_episode.mkv" (no season pattern)
- **THEN** the file is moved to `<PLEX_TV_DIR>/Breaking Bad/breaking_bad_episode.mkv`

### Requirement: Organizer extracts multi-part archives before organizing
The system SHALL detect archive files (`.rar`, `.001`, `.zip`, `.7z`) among downloaded files and extract them before organizing the extracted contents.

#### Scenario: Split RAR archive is extracted and organized
- **WHEN** a movie download completes with files "movie.part1.rar", "movie.part2.rar"
- **THEN** the system extracts the archive, organizes the extracted media files to the Plex folder, and discards the archive files

#### Scenario: Non-archive files are organized directly
- **WHEN** a download completes with a single .mkv file
- **THEN** the file is moved directly to the Plex folder without extraction

### Requirement: Organizer cleans up temp directory after organizing
The system SHALL delete the temporary download directory and its contents after all files have been organized (or extracted and organized).

#### Scenario: Temp directory removed after successful organization
- **WHEN** all files from a download have been moved to their Plex destinations
- **THEN** the temporary download directory for that download is deleted

### Requirement: Organizer updates download status on completion
The system SHALL set the download status to "complete" after successful file organization, and to "failed" with an error message if organization fails.

#### Scenario: Successful organization marks download complete
- **WHEN** all files are moved to Plex folders successfully
- **THEN** the download status is set to "complete" and file_paths is updated with the final destination paths

#### Scenario: Organization failure marks download failed
- **WHEN** file move fails (e.g., permission error, disk full)
- **THEN** the download status is set to "failed" with a descriptive error_message
