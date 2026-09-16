## ADDED Requirements

### Requirement: FileBot organizer moves completed downloads to Plex directories
The system SHALL use the FileBot CLI to move completed downloads to Plex-compatible folder structures. For movies, files SHALL be moved to `<PLEX_MOVIES_DIR>` using the `{plex}` format string. For TV, files SHALL be moved to `<PLEX_TV_DIR>` using the `{plex}` format string. FileBot SHALL be invoked with `--action move`, `-non-strict`, and `--q <title>` to use the user-provided title as the lookup hint.

#### Scenario: Movie download organized by FileBot
- **WHEN** a movie download with title "Inception", year 2010 completes with file "Inception.2010.1080p.mkv"
- **THEN** FileBot is invoked with `--output <PLEX_MOVIES_DIR> --format "{plex}" --q "Inception" --action move -non-strict` and the file is moved to the Plex movie directory

#### Scenario: TV download organized by FileBot
- **WHEN** a TV download with title "Breaking Bad" completes with file "Breaking.Bad.S03E05.mkv"
- **THEN** FileBot is invoked with `--output <PLEX_TV_DIR> --format "{plex}" --q "Breaking Bad" --action move -non-strict` and the file is moved to the Plex TV directory

### Requirement: FileBot organizer extracts archives before renaming
The system SHALL detect archive files (`.rar`, `.zip`, `.7z`, `.001`) among the source file list and run `filebot -extract` on them before the rename step. Extracted files SHALL be written to a temporary directory. The rename step SHALL process both the temp directory (extracted files) and any non-archive source files together.

#### Scenario: Archive files are extracted before rename
- **WHEN** a download completes with files "movie.part1.rar" and "movie.part2.rar"
- **THEN** FileBot extracts the archives to a temp directory, then renames the extracted media files to the Plex output directory

#### Scenario: Non-archive files are renamed directly
- **WHEN** a download completes with a single "Movie.2024.1080p.mkv" file
- **THEN** FileBot skips extraction and renames the file directly to the Plex output directory

#### Scenario: Mixed archive and non-archive files
- **WHEN** a download has "movie.rar" and "subtitle.srt"
- **THEN** FileBot extracts the archive to a temp dir, then renames both the extracted files and "subtitle.srt" together to the Plex output directory

### Requirement: FileBot organizer cleans up temp directory after organizing
The system SHALL delete the temporary extraction directory after the rename step completes, whether or not it succeeded.

#### Scenario: Temp directory is cleaned up on success
- **WHEN** FileBot successfully extracts and renames files
- **THEN** the temp extraction directory is removed

#### Scenario: Temp directory is cleaned up on failure
- **WHEN** FileBot extraction or rename fails
- **THEN** the temp extraction directory is still removed and the error is propagated

### Requirement: FileBot organizer returns final destination paths
The system SHALL parse FileBot's stdout to collect the final destination path for each renamed file. The worker SHALL use these paths to update `DownloadFile.file_path` records. If stdout parsing yields no paths, the system SHALL fall back to scanning the output directory for files newer than the pre-invocation timestamp.

#### Scenario: Final paths parsed from FileBot stdout
- **WHEN** FileBot outputs `[rename] From [/dl/Movie.mkv] to [/plex/Movie (2024)/Movie.mkv]`
- **THEN** the organizer returns `/plex/Movie (2024)/Movie.mkv` as the final path

#### Scenario: Fallback scan when stdout parse yields nothing
- **WHEN** FileBot succeeds but stdout contains no parseable rename lines
- **THEN** the organizer scans the output directory for files newer than before the invocation and returns those paths

### Requirement: FileBot organizer reports failure on non-zero exit
The system SHALL treat a non-zero FileBot exit code as a failure. The FileBot stderr output SHALL be included in the error message stored on the download record.

#### Scenario: FileBot exits non-zero
- **WHEN** FileBot exits with a non-zero exit code
- **THEN** the download is marked as "failed" with an error_message containing the FileBot stderr output

### Requirement: FileBot binary path is configurable
The system SHALL read the FileBot executable path from `MEGAQUEUE_FILEBOT_BIN` (default: `filebot`). This allows the binary name or full path to be specified explicitly (e.g., `filebot.exe` on Windows or `/usr/local/bin/filebot`).

#### Scenario: Custom FileBot binary path is used
- **WHEN** `MEGAQUEUE_FILEBOT_BIN` is set to `C:\Program Files\FileBot\filebot.exe`
- **THEN** the organizer invokes that path rather than the default `filebot`

#### Scenario: Default binary name is used when not configured
- **WHEN** `MEGAQUEUE_FILEBOT_BIN` is not set
- **THEN** the organizer invokes `filebot` (resolved via PATH)

### Requirement: Startup validates FileBot binary is accessible
The system SHALL verify at startup that the configured FileBot binary is callable by running `filebot --version`. If the binary is not found or exits non-zero, the application SHALL log a warning identifying the missing binary.

#### Scenario: FileBot binary is missing at startup
- **WHEN** `filebot --version` fails at startup
- **THEN** the application logs "FileBot binary not accessible at: <path> — file organization will fail" and continues starting up
