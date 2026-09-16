## MODIFIED Requirements

### Requirement: Worker matches folder-split entries via sourceUrl and folder ID
The worker SHALL use a three-tier matching strategy when correlating download manager status entries to `DownloadFile` records:
1. First match by normalized URL (for single file downloads)
2. For unmatched entries, match by `sourceUrl` field if present (the download manager returns the original folder URL as `sourceUrl` on each per-file entry from folder splits)
3. For unmatched entries, extract the folder ID from the `###n={folderId}` suffix in the entry's URL and match against `DownloadFile` records whose URL is a recognised folder URL with the same folder ID (backward compatibility fallback). Recognised folder URL formats are `https://mega.nz/folder/{folderId}#{key}` (new format) and `https://mega.nz/#F!{folderId}!{key}` (old format).

#### Scenario: Single file matched by URL
- **WHEN** the download manager reports an entry with URL matching a `DownloadFile`'s URL
- **THEN** the entry is matched to that `DownloadFile` via URL normalization

#### Scenario: Folder-split matched by sourceUrl
- **WHEN** the download manager returns 3 entries each with `sourceUrl: "https://mega.nz/folder/abc#xyz"`
- **AND** a `DownloadFile` exists with URL `https://mega.nz/folder/abc#xyz`
- **THEN** all 3 entries are matched to that `DownloadFile` via Tier 2

#### Scenario: Fallback to folder-ID matching when sourceUrl is absent (new format)
- **WHEN** the download manager returns entries without `sourceUrl` whose URLs carry `###n=abc`
- **AND** a `DownloadFile` exists with URL `https://mega.nz/folder/abc#xyz`
- **THEN** the worker falls back to Tier 3 and matches the entries to that `DownloadFile`

#### Scenario: Fallback to folder-ID matching when sourceUrl is absent (old format)
- **WHEN** the download manager returns entries without `sourceUrl` whose URLs carry `###n=abc`
- **AND** a `DownloadFile` exists with URL `https://mega.nz/#F!abc!xyz`
- **THEN** the worker falls back to Tier 3 and matches the entries to that `DownloadFile`

#### Scenario: Folder-split progress aggregation
- **WHEN** a `DownloadFile` (folder URL) matches 3 the download manager entries with varying progress
- **THEN** the worker aggregates `progress_bytes` and `total_bytes` across all matched entries, and the `DownloadFile` is only marked "finished" when all matched entries report `finished: true`

#### Scenario: Non-folder entry with no match is not affected
- **WHEN** the download manager returns an entry whose URL has no `###n=` suffix and does not match any `DownloadFile` URL
- **THEN** the entry is ignored (not matched to any record)

### Requirement: Worker updates per-file progress from the download manager status
The system SHALL match each the download manager download entry to a DownloadFile record by normalized mega.nz URL (or by folder ID for folder-split entries) and update that file's progress_bytes, total_bytes, speed, name, and status.

For folder-split downloads, the worker SHALL first check whether child DownloadFile records exist for the parent folder DownloadFile. If children do not yet exist, the worker SHALL create them (one per the download manager entry) with parent_id set to the folder DownloadFile. Each child record SHALL then be updated independently from its matched the download manager entry. The parent folder DownloadFile is no longer directly updated from the download manager after expansion.

A DownloadFile is treated as a folder for the purpose of expansion if its URL matches either `https://mega.nz/folder/{folderId}#{key}` (new format) or `https://mega.nz/#F!{folderId}!{key}` (old format). Both formats SHALL be expanded identically.

When a re-check adds new DownloadFile children to an already-expanded folder, the worker SHALL submit only the new files' URLs to the download manager and SHALL NOT re-submit URLs for existing children that are already `finished`.

#### Scenario: File progress is updated
- **WHEN** the download manager reports a file at 500MB of 1.2GB with speed 5MB/s
- **THEN** the matching DownloadFile's progress_bytes, total_bytes, and speed are updated

#### Scenario: File name is populated from the download manager
- **WHEN** the download manager reports a download with name "Movie.2024.1080p.mkv"
- **THEN** the matching DownloadFile's name field is set to that value

#### Scenario: Folder-split creates child DownloadFile records on first tick (new format)
- **WHEN** the download manager splits folder URL `https://mega.nz/folder/abc#xyz` into 3 file entries and no child DownloadFile records exist yet
- **THEN** the worker creates 3 child DownloadFile records linked to the folder DownloadFile via parent_id, each initialized with the the download manager entry's URL, name, and progress data

#### Scenario: Folder-split creates child DownloadFile records on first tick (old format)
- **WHEN** the download manager splits folder URL `https://mega.nz/#F!abc!xyz` into 3 file entries and no child DownloadFile records exist yet
- **THEN** the worker creates 3 child DownloadFile records linked to the folder DownloadFile via parent_id, each initialized with the the download manager entry's URL, name, and progress data

#### Scenario: Folder-split expansion is idempotent
- **WHEN** the download manager splits a folder URL into 3 file entries and child records already exist from a previous tick
- **THEN** the worker updates the existing child records and does not create duplicates

#### Scenario: Re-checked files are submitted without re-submitting finished files
- **WHEN** a re-check adds 2 new DownloadFile children to a folder that already has 5 finished children
- **THEN** only the 2 new file URLs are submitted to the download manager for download

### Requirement: Download status is derived from file statuses
The system SHALL derive the Download's overall status from its files and metadata confidence: all leaf files finished AND `metadata_confidence="high"` → "processing"; all leaf files finished AND `metadata_confidence="low"` → "needs_review"; all leaf files failed → "failed"; any leaf file downloading or finished (with others still queued) → "downloading"; otherwise → "queued". Once a download is in `needs_review`, the worker SHALL NOT change its status back to `downloading` or `processing` automatically — only an explicit transition driven by the resolve route SHALL move it to `processing`.

When a re-check adds new `queued` files to a `complete` Download, the presence of non-finished leaf files SHALL cause the derived status to become `downloading` (since some files are finished and new ones are queued/downloading).

#### Scenario: All files complete with high confidence triggers processing
- **WHEN** a download has 3 files, all transition to "finished", and `metadata_confidence="high"`
- **THEN** the download's status becomes "processing" and post-processing is triggered

#### Scenario: All files complete with low confidence triggers needs_review
- **WHEN** a download has 3 files, all transition to "finished", and `metadata_confidence="low"`
- **THEN** the download's status becomes "needs_review" and post-processing is NOT triggered

#### Scenario: Partial failure keeps download active
- **WHEN** a download has 3 files, 1 has finished, 1 is downloading, and 1 has failed
- **THEN** the download's status remains "downloading"

#### Scenario: needs_review is not auto-cleared
- **WHEN** a download is in `needs_review` and the worker polls
- **THEN** the worker does not change the status; the user must submit the resolve form to move it to `processing`

#### Scenario: Re-check transitions complete download back to downloading
- **WHEN** a `complete` Download has 5 finished files and a re-check adds 2 queued files
- **THEN** the derived status becomes `downloading` because not all leaf files are finished
