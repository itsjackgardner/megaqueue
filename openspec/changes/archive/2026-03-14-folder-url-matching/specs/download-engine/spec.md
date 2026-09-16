## MODIFIED Requirements

### Requirement: Megabasterd API returns sourceUrl and path on each status entry
The megabasterd fork's `/status` endpoint SHALL include the following additional field on each download entry:
- `path`: The relative path from the download directory (e.g., `FolderName/file.mkv` for folder contents, `file.mkv` for single files)

Note: `sourceUrl` is NOT returned by megabasterd. Per-file entries produced by folder splits embed the source folder ID in the URL via the `###n={folderId}` suffix instead.

#### Scenario: Single file download status
- **WHEN** megabasterd downloads a single file URL `https://mega.nz/file/abc#xyz`
- **THEN** the status entry includes `path: "Movie.2024.1080p.mkv"`

#### Scenario: Folder URL split into per-file entries
- **WHEN** megabasterd receives folder URL `https://mega.nz/folder/abc#xyz` containing 3 files
- **THEN** the status response includes 3 entries, each with a per-file URL of the form `https://mega.nz/#N!{fileId}!{fileKey}###n=abc` and a `path` like `"FolderName/file1.mkv"`, `"FolderName/file2.mkv"`, etc.

### Requirement: Worker matches folder-split entries via folder ID
The worker SHALL use a three-tier matching strategy when correlating megabasterd status entries to `DownloadFile` records:
1. First match by normalized URL (for single file downloads)
2. For unmatched entries, match by `sourceUrl` field if present (forward-compatibility shim; currently not returned by megabasterd)
3. For unmatched entries, extract the folder ID from the `###n={folderId}` suffix in the megabasterd entry's URL and match against `DownloadFile` records whose URL is a `mega.nz/folder/{folderId}` URL with the same folder ID

#### Scenario: Single file matched by URL
- **WHEN** megabasterd reports an entry with URL matching a `DownloadFile`'s URL
- **THEN** the entry is matched to that `DownloadFile` via URL normalization

#### Scenario: Folder-split files matched by folder ID
- **WHEN** megabasterd splits a folder URL `https://mega.nz/folder/LAlWVZbQ#key` into 8 per-file entries, each with URL containing `###n=LAlWVZbQ`
- **THEN** all 8 entries are matched to the single `DownloadFile` whose URL is `https://mega.nz/folder/LAlWVZbQ#key`

#### Scenario: Folder-split progress aggregation
- **WHEN** a `DownloadFile` (folder URL) matches 3 megabasterd entries with varying progress
- **THEN** the worker aggregates `progress_bytes` and `total_bytes` across all matched entries, and the `DownloadFile` is only marked "finished" when all matched entries report `finished: true`

#### Scenario: Non-folder entry with no match is not affected
- **WHEN** megabasterd returns an entry whose URL has no `###n=` suffix and does not match any `DownloadFile` URL
- **THEN** the entry is ignored (not matched to any record)

### Requirement: Worker normalizes mega.nz URLs for matching
The system SHALL normalize mega.nz URLs before matching, handling both old format (`https://mega.nz/#!{id}!{key}`), new format (`https://mega.nz/file/{id}#{key}`), and folder-file format (`https://mega.nz/#N!{id}!{key}###n={folderId}`) by extracting the file ID and key. Folder URLs (`https://mega.nz/folder/{id}#{key}`) are identified separately for folder-ID-based matching and are not normalized via the file ID/key path.

#### Scenario: Old and new URL formats match
- **WHEN** megaqueue stores `https://mega.nz/file/abc#xyz` and megabasterd returns `https://mega.nz/#!abc!xyz`
- **THEN** the worker correctly matches them as the same file

#### Scenario: Folder-file URL is normalized by stripping folder suffix
- **WHEN** megabasterd returns `https://mega.nz/#N!fileId!fileKey###n=folderId`
- **THEN** the worker strips `###n=folderId` before normalizing to `fileId#fileKey` for Tier 1 matching, and also extracts `folderId` for Tier 3 matching
