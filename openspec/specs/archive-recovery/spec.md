### Requirement: Archive extraction validates unrar availability and output
Before extracting a `.rar` or `.001` archive, the system SHALL verify that the `unrar` binary is available by checking `rarfile.UNRAR_TOOL` resolves to an executable on PATH. If `unrar` is not found, the system SHALL raise an error with a clear message naming the missing binary. After `extractall()` completes, the system SHALL verify the temp directory contains at least one file. If extraction produced no files, the system SHALL raise an error including diagnostic details (archive path, temp directory path, which unrar tool was configured).

#### Scenario: unrar not on PATH
- **WHEN** a `.rar` archive needs extraction and `unrar` is not on PATH
- **THEN** the system SHALL raise an error with message containing "unrar" and instructions to install it

#### Scenario: extractall succeeds but no files produced
- **WHEN** `rarfile.RarFile.extractall()` completes without error but the temp directory is empty
- **THEN** the system SHALL raise an error with the archive name, temp directory path, and the configured unrar tool path

#### Scenario: extractall succeeds with files
- **WHEN** `rarfile.RarFile.extractall()` produces files in the temp directory
- **THEN** the system SHALL proceed with organisation as normal

### Requirement: Pre-extracted archive fallback during source path resolution
When a leaf file's expected source path does not exist and the filename has an archive extension (`.rar`, `.zip`, `.7z`, `.001`), the system SHALL look for a directory in `DOWNLOAD_DIR` whose name matches the archive's stem (filename without extension). If such a directory exists and contains at least one media file, the system SHALL use that directory as the source for organisation, skipping archive extraction.

#### Scenario: Manually extracted rar directory found
- **WHEN** leaf file name is `H2OBoy.rar` and `DOWNLOAD_DIR/H2OBoy.rar` does not exist
- **AND** `DOWNLOAD_DIR/H2OBoy/` exists and contains `The Waterboy (1998).mkv`
- **THEN** the system SHALL use the directory contents for organisation without attempting extraction

#### Scenario: No fallback directory exists
- **WHEN** leaf file name is `H2OBoy.rar` and `DOWNLOAD_DIR/H2OBoy.rar` does not exist
- **AND** `DOWNLOAD_DIR/H2OBoy/` does not exist
- **THEN** the system SHALL fail with the original `FileNotFoundError`

#### Scenario: Fallback directory is empty or has no media files
- **WHEN** leaf file name is `movie.rar` and `DOWNLOAD_DIR/movie.rar` does not exist
- **AND** `DOWNLOAD_DIR/movie/` exists but contains only `.txt` and `.nfo` files
- **THEN** the system SHALL fail with a descriptive error rather than organising non-media files

#### Scenario: Non-archive file missing has no fallback
- **WHEN** leaf file name is `movie.mkv` and `DOWNLOAD_DIR/movie.mkv` does not exist
- **THEN** the system SHALL fail with `FileNotFoundError` immediately (no directory fallback)

### Requirement: Pre-extracted content organised using existing routing logic
When organising from a pre-extracted directory, the system SHALL route each file within the directory using the same movie/TV routing rules as normally-extracted archive content. The largest media file SHALL be treated as the main feature (for movies) and associated with the leaf file's `file_path`.

#### Scenario: Pre-extracted movie directory organised to Plex
- **WHEN** pre-extracted directory `H2OBoy/` contains `The Waterboy (1998).mkv` (1.8 GB) and `Sample.mkv` (50 MB)
- **THEN** `The Waterboy (1998).mkv` is routed as the main feature to `PLEX_MOVIES_DIR/The Waterboy (1998)/The Waterboy (1998).mkv`
- **AND** `Sample.mkv` is routed as an extra to `PLEX_MOVIES_DIR/The Waterboy (1998)/Featurettes/Sample.mkv`

#### Scenario: Pre-extracted TV episodes organised to Plex
- **WHEN** pre-extracted directory contains `Show.S01E01.mkv` and `Show.S01E02.mkv`
- **THEN** each episode is routed to its correct season folder using standard TV routing rules

### Requirement: Media file detection uses video and subtitle extensions
The system SHALL recognise the following extensions as media files when validating a pre-extracted directory: `.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.srt`, `.sub`, `.idx`, `.ass`, `.ssa`. A directory SHALL be considered valid for fallback if it contains at least one file with a media extension.

#### Scenario: Directory with video files is valid
- **WHEN** a fallback directory contains `movie.mkv`
- **THEN** the directory is accepted as valid pre-extracted content

#### Scenario: Directory with only subtitles is valid
- **WHEN** a fallback directory contains `movie.srt` but no video files
- **THEN** the directory is accepted as valid pre-extracted content

#### Scenario: Directory with only non-media files is rejected
- **WHEN** a fallback directory contains only `readme.txt` and `info.nfo`
- **THEN** the directory is rejected and the system fails with a descriptive error
