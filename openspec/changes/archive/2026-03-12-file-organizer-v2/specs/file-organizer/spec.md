## ADDED Requirements

### Requirement: Organizer discovers source files from DownloadFile paths
The system SHALL locate source files by reading `file_path` from each `DownloadFile` record. If a `file_path` points to a directory, the organizer SHALL collect all files within that directory (non-recursive for media files, recursive only for archive detection).

#### Scenario: Single file download
- **WHEN** a download has one `DownloadFile` with `file_path` pointing to a single `.mkv` file
- **THEN** the organizer collects that one file for routing

#### Scenario: Folder download with multiple files
- **WHEN** a download has one `DownloadFile` with `file_path` pointing to a directory containing 5 `.mkv` files
- **THEN** the organizer collects all 5 files for routing

#### Scenario: Multiple URL download
- **WHEN** a download has 3 `DownloadFile` records, each with a `file_path` pointing to a different file
- **THEN** the organizer collects all 3 files for routing

#### Scenario: Source path does not exist
- **WHEN** a `DownloadFile.file_path` points to a path that does not exist on disk
- **THEN** the organizer SHALL raise a `FileNotFoundError` with a message identifying the missing path

### Requirement: Organizer consolidates archive parts across folders before extraction
The system SHALL detect archive files across all source directories from a download. When archive parts are found in multiple directories, the system SHALL copy all archive files into a single temporary directory before extraction.

#### Scenario: Archive parts split across two folders
- **WHEN** a download has two folder URLs, folder A containing `movie.part1.rar` and folder B containing `movie.part2.rar`
- **THEN** the organizer copies both parts into a temp directory and extracts them together

#### Scenario: Archive parts in a single folder
- **WHEN** a download has one folder URL containing `movie.part1.rar`, `movie.part2.rar`, `movie.part3.rar`
- **THEN** the organizer extracts directly from that folder without consolidation

#### Scenario: Mixed archive and non-archive files
- **WHEN** a folder contains `movie.rar` and `subtitle.srt`
- **THEN** the organizer extracts the archive and also includes `subtitle.srt` in the files to route

### Requirement: Organizer routes each TV episode file to the correct season folder independently
The system SHALL analyze each individual file's name for season information using the `SxxExx` pattern. Each file SHALL be routed to its detected season folder independently, even within the same download.

#### Scenario: Folder with episodes from multiple seasons
- **WHEN** a TV download folder contains `Show.S01E01.mkv`, `Show.S01E02.mkv`, and `Show.S02E01.mkv`
- **THEN** the first two files are moved to `<PLEX_TV_DIR>/<Title>/Season 01/` and the third to `<PLEX_TV_DIR>/<Title>/Season 02/`

#### Scenario: Folder with episodes from one season
- **WHEN** a TV download folder contains `Show.S03E01.mkv`, `Show.S03E02.mkv`, `Show.S03E03.mkv`
- **THEN** all three files are moved to `<PLEX_TV_DIR>/<Title>/Season 03/`

#### Scenario: Episode file without season pattern
- **WHEN** a TV download folder contains `show_episode_unknown.mkv` with no `SxxExx` pattern
- **THEN** the file is moved to `<PLEX_TV_DIR>/<Title>/` (show root)

### Requirement: Organizer cleans up source files after successful organization
The system SHALL delete all source files and directories from the megabasterd download directory only after every file has been successfully moved to its Plex destination. If any file move fails, cleanup SHALL NOT occur.

#### Scenario: All files organized successfully
- **WHEN** a download with 3 source files has all 3 successfully moved to Plex directories
- **THEN** the source directory in the megabasterd download path is deleted

#### Scenario: One file fails to move
- **WHEN** a download with 3 source files has 2 successfully moved but 1 fails (e.g., permission error)
- **THEN** no source files or directories are deleted and the download is marked as failed

### Requirement: Organizer returns organized file paths for all placed files
The system SHALL return a list of all final destination paths for files that were organized. The worker SHALL update each `DownloadFile.file_path` with the final destination path.

#### Scenario: Multi-episode download paths updated
- **WHEN** a TV download with 5 episodes is organized to various season folders
- **THEN** the organizer returns 5 destination paths and the worker updates file records accordingly

## MODIFIED Requirements

### Requirement: Organizer moves movie files to Plex movie folder structure
The system SHALL move completed movie downloads to `<PLEX_MOVIES_DIR>/<Title> (<Year>)/<filename>`. When a download contains multiple files (from a folder download or multiple URLs), each non-archive media file SHALL be placed in the same movie folder.

#### Scenario: Movie with year is organized
- **WHEN** a download with title "Inception", year 2010, media_type "movie" completes with file "Inception.2010.1080p.mkv"
- **THEN** the file is moved to `<PLEX_MOVIES_DIR>/Inception (2010)/Inception.2010.1080p.mkv`

#### Scenario: Movie without year is organized
- **WHEN** a download with title "Inception", no year, media_type "movie" completes
- **THEN** the file is moved to `<PLEX_MOVIES_DIR>/Inception/<filename>`

#### Scenario: Movie folder download with extras
- **WHEN** a movie folder download contains "Movie.2024.1080p.mkv" and "Movie.2024.1080p.srt"
- **THEN** both files are moved to `<PLEX_MOVIES_DIR>/Movie (2024)/`

### Requirement: Organizer moves TV files to Plex TV folder structure
The system SHALL move completed TV downloads to `<PLEX_TV_DIR>/<Title>/Season XX/<filename>`. If season cannot be determined from the filename, files are placed directly under `<Title>/`. Each file in a multi-file download SHALL be routed independently based on its own filename.

#### Scenario: TV episode is organized with season detection
- **WHEN** a download with title "Breaking Bad", media_type "tv" completes with file "Breaking.Bad.S03E05.mkv"
- **THEN** the file is moved to `<PLEX_TV_DIR>/Breaking Bad/Season 03/Breaking.Bad.S03E05.mkv`

#### Scenario: TV file without season info
- **WHEN** a download with title "Breaking Bad", media_type "tv" completes with file "breaking_bad_episode.mkv" (no season pattern)
- **THEN** the file is moved to `<PLEX_TV_DIR>/Breaking Bad/breaking_bad_episode.mkv`

### Requirement: Organizer extracts multi-part archives before organizing
The system SHALL detect archive files (`.rar`, `.001`, `.zip`, `.7z`) among downloaded files and extract them before organizing the extracted contents. When archive parts are spread across multiple source directories, they SHALL be consolidated into a single temp directory before extraction.

#### Scenario: Split RAR archive is extracted and organized
- **WHEN** a movie download completes with files "movie.part1.rar", "movie.part2.rar"
- **THEN** the system extracts the archive, organizes the extracted media files to the Plex folder, and discards the archive files

#### Scenario: Non-archive files are organized directly
- **WHEN** a download completes with a single .mkv file
- **THEN** the file is moved directly to the Plex folder without extraction

#### Scenario: Archive parts across multiple folders
- **WHEN** a download has 3 folder URLs, each containing one part of a split RAR archive
- **THEN** the system consolidates all parts into a temp directory, extracts them, and organizes the result
