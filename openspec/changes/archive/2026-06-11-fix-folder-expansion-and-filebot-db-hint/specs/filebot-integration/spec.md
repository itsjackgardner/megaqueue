## MODIFIED Requirements

### Requirement: FileBot organizer moves completed downloads to Plex directories
The system SHALL use the FileBot CLI to move completed downloads to Plex-compatible folder structures. For movies, files SHALL be moved to `<PLEX_MOVIES_DIR>` using the `{plex}` format string. For TV, files SHALL be moved to `<PLEX_TV_DIR>` using the `{plex}` format string. FileBot SHALL be invoked with `--action move`, `-non-strict`, `--q <title>` to use the user-provided title as the lookup hint, and `--db <database>` to force the lookup database based on the download's `media_type`. The database SHALL be `TheMovieDB` for `media_type=movie` and `TheTVDB` for `media_type=tv`. The explicit `--db` argument prevents FileBot's auto-detector from picking the wrong renamer (e.g., classifying a movie's bonus features as TV episodes).

#### Scenario: Movie download organized by FileBot
- **WHEN** a movie download with title "Inception", year 2010 completes with file "Inception.2010.1080p.mkv"
- **THEN** FileBot is invoked with `--output <PLEX_MOVIES_DIR> --format "{plex}" --q "Inception" --db TheMovieDB --action move -non-strict` and the file is moved to the Plex movie directory

#### Scenario: TV download organized by FileBot
- **WHEN** a TV download with title "Breaking Bad" completes with file "Breaking.Bad.S03E05.mkv"
- **THEN** FileBot is invoked with `--output <PLEX_TV_DIR> --format "{plex}" --q "Breaking Bad" --db TheTVDB --action move -non-strict` and the file is moved to the Plex TV directory

#### Scenario: Movie with bonus features uses movie database
- **WHEN** a movie download includes the main feature plus extras (trailer, featurette, interview clips) where some filenames lack year/quality tags
- **THEN** FileBot is invoked with `--db TheMovieDB` and does not attempt episode lookup against any TV database
