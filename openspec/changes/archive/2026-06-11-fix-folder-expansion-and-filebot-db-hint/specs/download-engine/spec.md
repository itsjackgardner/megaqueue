## MODIFIED Requirements

### Requirement: Worker matches folder-split entries via sourceUrl and folder ID
The worker SHALL use a three-tier matching strategy when correlating megabasterd status entries to `DownloadFile` records:
1. First match by normalized URL (for single file downloads)
2. For unmatched entries, match by `sourceUrl` field if present (megabasterd returns the original folder URL as `sourceUrl` on each per-file entry from folder splits)
3. For unmatched entries, extract the folder ID from the `###n={folderId}` suffix in the megabasterd entry's URL and match against `DownloadFile` records whose URL is a recognised folder URL with the same folder ID (backward compatibility fallback). Recognised folder URL formats are `https://mega.nz/folder/{folderId}#{key}` (new format) and `https://mega.nz/#F!{folderId}!{key}` (old format).

#### Scenario: Single file matched by URL
- **WHEN** megabasterd reports an entry with URL matching a `DownloadFile`'s URL
- **THEN** the entry is matched to that `DownloadFile` via URL normalization

#### Scenario: Folder-split matched by sourceUrl
- **WHEN** megabasterd returns 3 entries each with `sourceUrl: "https://mega.nz/folder/abc#xyz"`
- **AND** a `DownloadFile` exists with URL `https://mega.nz/folder/abc#xyz`
- **THEN** all 3 entries are matched to that `DownloadFile` via Tier 2

#### Scenario: Fallback to folder-ID matching when sourceUrl is absent (new format)
- **WHEN** megabasterd returns entries without `sourceUrl` whose URLs carry `###n=abc`
- **AND** a `DownloadFile` exists with URL `https://mega.nz/folder/abc#xyz`
- **THEN** the worker falls back to Tier 3 and matches the entries to that `DownloadFile`

#### Scenario: Fallback to folder-ID matching when sourceUrl is absent (old format)
- **WHEN** megabasterd returns entries without `sourceUrl` whose URLs carry `###n=abc`
- **AND** a `DownloadFile` exists with URL `https://mega.nz/#F!abc!xyz`
- **THEN** the worker falls back to Tier 3 and matches the entries to that `DownloadFile`

#### Scenario: Folder-split progress aggregation
- **WHEN** a `DownloadFile` (folder URL) matches 3 megabasterd entries with varying progress
- **THEN** the worker aggregates `progress_bytes` and `total_bytes` across all matched entries, and the `DownloadFile` is only marked "finished" when all matched entries report `finished: true`

#### Scenario: Non-folder entry with no match is not affected
- **WHEN** megabasterd returns an entry whose URL has no `###n=` suffix and does not match any `DownloadFile` URL
- **THEN** the entry is ignored (not matched to any record)

### Requirement: Worker updates per-file progress from megabasterd status
The system SHALL match each megabasterd download entry to a DownloadFile record by normalized mega.nz URL (or by folder ID for folder-split entries) and update that file's progress_bytes, total_bytes, speed, name, and status.

For folder-split downloads, the worker SHALL first check whether child DownloadFile records exist for the parent folder DownloadFile. If children do not yet exist, the worker SHALL create them (one per megabasterd entry) with parent_id set to the folder DownloadFile. Each child record SHALL then be updated independently from its matched megabasterd entry. The parent folder DownloadFile is no longer directly updated from megabasterd after expansion.

A DownloadFile is treated as a folder for the purpose of expansion if its URL matches either `https://mega.nz/folder/{folderId}#{key}` (new format) or `https://mega.nz/#F!{folderId}!{key}` (old format). Both formats SHALL be expanded identically.

#### Scenario: File progress is updated
- **WHEN** megabasterd reports a file at 500MB of 1.2GB with speed 5MB/s
- **THEN** the matching DownloadFile's progress_bytes, total_bytes, and speed are updated

#### Scenario: File name is populated from megabasterd
- **WHEN** megabasterd reports a download with name "Movie.2024.1080p.mkv"
- **THEN** the matching DownloadFile's name field is set to that value

#### Scenario: Folder-split creates child DownloadFile records on first tick (new format)
- **WHEN** megabasterd splits folder URL `https://mega.nz/folder/abc#xyz` into 3 file entries and no child DownloadFile records exist yet
- **THEN** the worker creates 3 child DownloadFile records linked to the folder DownloadFile via parent_id, each initialized with the megabasterd entry's URL, name, and progress data

#### Scenario: Folder-split creates child DownloadFile records on first tick (old format)
- **WHEN** megabasterd splits folder URL `https://mega.nz/#F!abc!xyz` into 3 file entries and no child DownloadFile records exist yet
- **THEN** the worker creates 3 child DownloadFile records linked to the folder DownloadFile via parent_id, each initialized with the megabasterd entry's URL, name, and progress data

#### Scenario: Folder-split expansion is idempotent
- **WHEN** megabasterd splits a folder URL into 3 file entries and child records already exist from a previous tick
- **THEN** the worker updates the existing child records and does not create duplicates
