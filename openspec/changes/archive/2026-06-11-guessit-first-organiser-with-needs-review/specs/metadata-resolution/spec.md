## ADDED Requirements

### Requirement: System extracts metadata from filenames using guessit
The system SHALL run `guessit` on each `DownloadFile.name` as soon as megabasterd reports it. Per-file results SHALL include at minimum `type` (`movie` or `episode`), `title`, and — where applicable — `year`, `season`, `episode`, `screen_size`, `source`, `video_codec`. The system SHALL NOT call any external metadata API (no TMDB, no TVDB, no network).

#### Scenario: Movie filename parsed
- **WHEN** megabasterd reports `Birth.2004.Criterion.1080p.BluRay.x265.HEVC.FLAC-SARTRE.mkv`
- **THEN** guessit returns `type=movie`, `title="Birth"`, `year=2004`, `screen_size="1080p"`, `source="BluRay"`

#### Scenario: TV episode filename parsed
- **WHEN** megabasterd reports `Gen.V.S02E06.1080p.10bit.WEBRip.6CH.x265.HEVC-PSA.mkv`
- **THEN** guessit returns `type=episode`, `title="Gen V"`, `season=2`, `episode=6`

#### Scenario: Bare extra filename parsed
- **WHEN** megabasterd reports `Trailer.mkv`
- **THEN** guessit returns `type=movie`, `title="Trailer"`, no `year`, no `screen_size`, no `source`

### Requirement: System aggregates per-file metadata into Download record
The system SHALL aggregate per-file guessit results into the parent `Download`'s `title`, `year`, and `media_type` fields on every poll tick where a file name is newly populated. The aggregation SHALL run in the worker, write back to the database, and set `metadata_source="guessit"`. The aggregation SHALL run BEFORE post-processing is triggered.

#### Scenario: TV folder aggregation
- **WHEN** a Download has 8 child files each parsed as `type=episode`, `title="Gen V"`, `season=2`, `episode=1..8`
- **THEN** the Download's `title="Gen V"`, `media_type="tv"`, `year=null`

#### Scenario: Movie folder aggregation
- **WHEN** a Download has 5 files where one is parsed `title="Birth", year=2004, screen_size="1080p"` and four others lack year/quality fields
- **THEN** the Download's `title="Birth"`, `year=2004`, `media_type="movie"`

#### Scenario: Aggregation updates as files resolve
- **WHEN** a folder download is mid-resolution and only 3 of 8 children have names
- **THEN** aggregation runs on the partial set and writes the best-effort title to the Download row; the next tick updates again when more children land

### Requirement: System detects movie main feature vs extras
For movie-typed downloads with multiple files, the system SHALL identify the main feature file as the one whose guessit result includes a `year` AND at least one of `screen_size`, `source`, or `video_codec`. If multiple files match that criterion, the largest by `total_bytes` SHALL win. All other movie-typed files in the same Download SHALL have `is_extra=True` set on their `DownloadFile` record. Single-file movie downloads SHALL have `is_extra=False`.

#### Scenario: Birth (2004) with featurettes
- **WHEN** a movie Download contains `Birth.2004.Criterion.1080p.mkv` (8.4 GB), `Trailer.mkv`, `Making Birth.mkv`, `The Cinematography of Birth.mkv`, `Jonathan Glazer and actor Nicole Kidman.mkv`
- **THEN** `Birth.2004.Criterion.1080p.mkv` is marked `is_extra=False` and the four others are marked `is_extra=True`

#### Scenario: Tied quality tags, largest file wins
- **WHEN** two files both report `year=2010, screen_size="1080p"` but one is 12 GB and the other 800 MB
- **THEN** the 12 GB file is `is_extra=False`, the 800 MB file is `is_extra=True`

#### Scenario: Single-file movie
- **WHEN** a movie Download has exactly one file
- **THEN** that file is `is_extra=False`

### Requirement: System scores metadata confidence
The system SHALL score the aggregated metadata as `high` or `low` and write to `Download.metadata_confidence`. Confidence is `high` when EITHER (a) the Download is TV, every leaf file's guessit result has both `season` and `episode`, and at least 80% of files agree on a single `title`; OR (b) the Download is a movie and a main feature file was identified by the year+quality rule. Confidence is `low` in all other cases, including: no consistent type across files, no year on any movie file, no S/E pattern on any TV file, or guessit returning no `title` for any file.

#### Scenario: Well-formed TV pack scores high
- **WHEN** 8 files all match `type=episode`, `title="Gen V"`, season 2, episodes 1–8
- **THEN** confidence is `high`

#### Scenario: Movie with main feature scores high
- **WHEN** a main feature is identified via the year+quality rule
- **THEN** confidence is `high` even if extras lack year/quality (the extras rule explains them)

#### Scenario: Movie with no year anywhere scores low
- **WHEN** none of the files in a movie-typed Download have a year in their filenames
- **THEN** confidence is `low`

#### Scenario: Mixed type scores low
- **WHEN** 3 of 5 files parse as `type=episode` and 2 parse as `type=movie`
- **THEN** confidence is `low`

### Requirement: User-provided metadata overrides guessit
When a user submits the resolve form for a `needs_review` Download, the system SHALL write the user-provided title/year/media_type/per-file `is_extra` flags, set `metadata_source="user"` and `metadata_confidence="high"`, and transition status to `processing`. User-provided values SHALL NOT be re-overwritten by subsequent guessit runs on the same Download.

#### Scenario: User confirms metadata
- **WHEN** a Download is in `needs_review` and the user submits `title="Birth", year=2004, media_type="movie"` plus an `is_extra=true` toggle on four child files
- **THEN** the Download writes those values with `metadata_source="user"`, `metadata_confidence="high"`, transitions to `processing`, and the worker picks it up on the next tick

#### Scenario: Re-guessit does not overwrite user values
- **WHEN** a Download has `metadata_source="user"` and a new file name is reported by megabasterd
- **THEN** guessit may set `is_extra` on the newly-named file but SHALL NOT change `title`, `year`, or `media_type` on the Download
