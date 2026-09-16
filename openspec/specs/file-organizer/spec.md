## MODIFIED Requirements

### Requirement: Organizer cleans up temp directory after organizing
The system SHALL delete the temporary extraction directory after the rename step completes, whether or not it succeeded. Source files in `DOWNLOAD_DIR` SHALL be removed by the organiser's move step and do not require separate cleanup. When organising from a pre-extracted directory, the system SHALL NOT delete the source directory — only move files out of it. If the directory becomes empty after all files are moved, it MAY be removed.

#### Scenario: Temp directory removed after successful organization
- **WHEN** the organiser successfully extracts archives and moves files to Plex
- **THEN** the temporary extraction directory is removed and the source files are gone (moved)

#### Scenario: Temp directory removed after failure
- **WHEN** the organiser fails during extraction or move
- **THEN** the temporary extraction directory is still removed and the error is propagated to mark the download as failed

#### Scenario: Pre-extracted directory preserved on partial success
- **WHEN** the organiser moves some files from a pre-extracted directory but fails on others
- **THEN** the pre-extracted directory is NOT deleted and unmoved files remain in place for manual recovery

### Requirement: Organizer updates download status on completion
The system SHALL set the download status to "complete" after successful file organization, and to "failed" with an error message if organization fails. The organiser SHALL only run when the Download status is `processing`; it SHALL NOT run for Downloads in `needs_review`.

#### Scenario: Successful organization marks download complete
- **WHEN** the organiser moves all files to Plex folders successfully
- **THEN** the download status is set to "complete" and file_path is updated on each DownloadFile with the final destination path

#### Scenario: Organization failure marks download failed
- **WHEN** the organiser raises an exception (e.g., file not found, permission error)
- **THEN** the download status is set to "failed" with a descriptive error_message

#### Scenario: needs_review blocks the organiser
- **WHEN** all files have finished but the Download is in `needs_review` (low metadata confidence)
- **THEN** the organiser does not run and the Download remains in `needs_review` until the user submits the resolve form

### Requirement: Organizer returns organized file paths for all placed files
The system SHALL return a list of all final destination paths for files that were organized. The worker SHALL update each `DownloadFile.file_path` with the final destination path.

#### Scenario: Multi-episode download paths updated
- **WHEN** a TV download with 5 episodes is organized to season folders
- **THEN** the organiser returns 5 destination paths and the worker updates file records accordingly

## ADDED Requirements

### Requirement: Organiser is hand-rolled (no external CLI)
The system SHALL organise files using a Python-only organiser module. The organiser SHALL NOT shell out to FileBot, Filebot, or any third-party media tool. Archive extraction SHALL use `rarfile` (with `unrar` system binary for `.rar`/`.001`), `zipfile` (stdlib, for `.zip`), and `py7zr` (pure Python, for `.7z`).

#### Scenario: No FileBot invocation
- **WHEN** the organiser runs against a finished download
- **THEN** no `subprocess.run([...filebot...])` call is made and the FileBot binary is not required to be installed

#### Scenario: Rar archive extracted via rarfile
- **WHEN** a download contains `movie.rar` (or `movie.part01.rar` + parts)
- **THEN** `rarfile` extracts to a temp directory before the move step runs

#### Scenario: Zip archive extracted via stdlib
- **WHEN** a download contains `movie.zip`
- **THEN** `zipfile` extracts to a temp directory before the move step runs

#### Scenario: 7z archive extracted via py7zr
- **WHEN** a download contains `movie.7z`
- **THEN** `py7zr` extracts to a temp directory before the move step runs

### Requirement: Movie main feature uses Plex movie naming
For movie Downloads, the leaf file with `is_extra=False` SHALL be moved to `<PLEX_MOVIES_DIR>/<Title> (<Year>)/<Title> (<Year>).<ext>`. If `Year` is null, the parent folder SHALL be `<Title>/` and the file `<Title>.<ext>`. The file extension SHALL be preserved from the source.

#### Scenario: Main feature with year
- **WHEN** the main feature is `Birth.2004.Criterion.1080p.mkv` and the Download has `title="Birth", year=2004`
- **THEN** it is moved to `<PLEX_MOVIES_DIR>/Birth (2004)/Birth (2004).mkv`

#### Scenario: Main feature without year
- **WHEN** the main feature is `Movie.mkv` and the Download has `title="Movie", year=null`
- **THEN** it is moved to `<PLEX_MOVIES_DIR>/Movie/Movie.mkv`

### Requirement: Movie extras land in Featurettes subfolder
For movie Downloads, leaf files with `is_extra=True` SHALL be moved to `<PLEX_MOVIES_DIR>/<Title> (<Year>)/Featurettes/<original-name>.<ext>`. The original filename SHALL be preserved (not renamed) so the user can identify which featurette is which. The `Featurettes/` subfolder name is Plex's recognised convention for local extras.

#### Scenario: Birth (2004) featurettes
- **WHEN** the Download `title="Birth", year=2004` has four files with `is_extra=true`: `Trailer.mkv`, `Making Birth.mkv`, `The Cinematography of Birth.mkv`, `Jonathan Glazer and actor Nicole Kidman.mkv`
- **THEN** all four are moved into `<PLEX_MOVIES_DIR>/Birth (2004)/Featurettes/` with their original filenames

#### Scenario: Movie with no extras has no Featurettes subfolder
- **WHEN** a movie Download has only one file (`is_extra=false`)
- **THEN** the destination folder contains only the main feature; no empty `Featurettes/` subfolder is created

### Requirement: TV episodes use Plex episode naming
For TV Downloads, every leaf file SHALL be moved to `<PLEX_TV_DIR>/<Title>/Season <NN>/<Title> - S<NN>E<NN>.<ext>`, where `<NN>` is zero-padded to two digits. Season and episode numbers come from per-file guessit results. If guessit returned no season for a file but the Download has `media_type=tv`, the file SHALL be flagged as a per-file failure with `error_message="No season/episode detected"` (not the whole Download).

When organising a re-checked Download, the organiser SHALL only process leaf files that do not already have a `file_path` set. Files from previous organisation runs (which already have `file_path` populated) SHALL be skipped.

#### Scenario: Standard episode placement
- **WHEN** a TV Download has `title="Gen V"` and file `Gen.V.S02E06.mkv` parsed `season=2, episode=6`
- **THEN** it is moved to `<PLEX_TV_DIR>/Gen V/Season 02/Gen V - S02E06.mkv`

#### Scenario: Multi-season pack
- **WHEN** a TV Download contains files spanning seasons 1 and 2
- **THEN** each file is routed to its correct season folder by its own guessit result

#### Scenario: Episode without S/E
- **WHEN** a TV Download has a file whose guessit returned no season/episode
- **THEN** that DownloadFile is marked failed with `error_message="No season/episode detected"` and the Download proceeds (other files are organised); the file remains in the download dir for manual handling

#### Scenario: Re-checked episodes skip already-organised files
- **WHEN** a re-checked TV Download has 5 files with `file_path` set and 2 new files with `file_path=null`
- **THEN** the organiser processes only the 2 new files and leaves the 5 existing files untouched

### Requirement: Organiser skips files whose destination already exists
When the organiser computes a destination path for a file and that path already exists on disk, the file SHALL be skipped rather than overwriting or failing. The DownloadFile's `file_path` SHALL still be set to the destination path (marking it as organised). This handles edge cases where a file was manually placed or a previous partial run left files in place.

#### Scenario: Destination file already exists
- **WHEN** the organiser computes destination `TV Shows/Gen V/Season 02/Gen V - S02E06.mkv` and that file already exists on disk
- **THEN** the source file is not moved, the DownloadFile's `file_path` is set to the destination, and no error is raised

#### Scenario: Destination does not exist, normal move
- **WHEN** the organiser computes a destination path that does not exist
- **THEN** the file is moved to the destination normally
