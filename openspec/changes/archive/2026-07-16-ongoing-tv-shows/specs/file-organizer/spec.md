## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Organiser skips files whose destination already exists
When the organiser computes a destination path for a file and that path already exists on disk, the file SHALL be skipped rather than overwriting or failing. The DownloadFile's `file_path` SHALL still be set to the destination path (marking it as organised). This handles edge cases where a file was manually placed or a previous partial run left files in place.

#### Scenario: Destination file already exists
- **WHEN** the organiser computes destination `TV Shows/Gen V/Season 02/Gen V - S02E06.mkv` and that file already exists on disk
- **THEN** the source file is not moved (or is cleaned up from the download dir), the DownloadFile's `file_path` is set to the destination, and no error is raised

#### Scenario: Destination does not exist, normal move
- **WHEN** the organiser computes a destination path that does not exist
- **THEN** the file is moved to the destination normally
