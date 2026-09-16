## ADDED Requirements

### Requirement: User can re-check a completed folder download for new files
The system SHALL provide a "Re-check" action on completed Downloads that have at least one folder URL among their top-level files. When triggered, the system SHALL query megabasterd's folder-list endpoint for the current contents of each folder URL, compare against already-known leaf DownloadFile records (by filename), and create new child DownloadFile records for any files not already present. The Download's status SHALL transition from `complete` back to `downloading`, and the new files SHALL be submitted to megabasterd for download.

#### Scenario: Re-check finds new episodes
- **WHEN** a completed TV Download has folder URL `https://mega.nz/folder/abc#key` with 5 existing leaf files, and the folder now contains 7 files
- **THEN** 2 new child DownloadFile records are created under the folder parent, the Download status becomes `downloading`, and only the 2 new files are submitted to megabasterd

#### Scenario: Re-check finds no new files
- **WHEN** a completed Download is re-checked and the folder contents match all existing leaf files
- **THEN** no new DownloadFile records are created, the Download status remains `complete`, and the user is informed that no new files were found

#### Scenario: Re-check on a download with non-folder links
- **WHEN** a completed Download has only single-file URLs (no folder links)
- **THEN** the "Re-check" action is not available in the UI

#### Scenario: Re-check while download is already active
- **WHEN** a user attempts to re-check a Download that is in `downloading`, `queued`, or `processing` status
- **THEN** the action is rejected (the button is not shown for non-complete downloads)

### Requirement: Megabasterd client supports folder content listing
The megabasterd client SHALL expose a `folder_list(url)` method that calls megabasterd's `GET /folder-list` endpoint with the folder URL as a query parameter. The endpoint SHALL return a JSON array of objects, each with at least `name` (string) and `url` (string) fields representing individual files within the folder. The client method SHALL return this list to the caller.

#### Scenario: Folder list returns file metadata
- **WHEN** `folder_list("https://mega.nz/folder/abc#key")` is called and the folder contains 3 files
- **THEN** the client returns a list of 3 objects with `name` and `url` fields

#### Scenario: Folder list for empty folder
- **WHEN** `folder_list` is called for a folder that contains no files
- **THEN** the client returns an empty list

#### Scenario: Folder list for invalid URL
- **WHEN** `folder_list` is called with an invalid or expired folder URL
- **THEN** the client raises an appropriate error that the caller can handle

### Requirement: New files from re-check are diffed by filename
The system SHALL determine which files are "new" by comparing the `name` field from the folder listing against the `name` field of existing leaf DownloadFile records under the same parent. A file is considered new if no existing leaf record has a matching name. URL-based matching SHALL NOT be used for the diff because megabasterd may generate different per-file URLs on each folder listing.

#### Scenario: Filename match prevents duplicate download
- **WHEN** the folder listing returns a file named `Show.S01E03.mkv` and an existing leaf DownloadFile has `name="Show.S01E03.mkv"`
- **THEN** that file is not considered new and no duplicate record is created

#### Scenario: New filename creates new record
- **WHEN** the folder listing returns a file named `Show.S01E08.mkv` and no existing leaf DownloadFile has that name
- **THEN** a new child DownloadFile is created with that name and URL

### Requirement: Re-check preserves existing file state
When a re-check adds new files to a Download, all existing DownloadFile records SHALL remain unchanged — their `status`, `file_path`, `progress_bytes`, and other fields SHALL NOT be modified. Only the Download-level status transitions back to `downloading`.

#### Scenario: Completed files retain their state after re-check
- **WHEN** a Download with 5 finished files is re-checked and 2 new files are added
- **THEN** the 5 existing files still have `status="finished"` and their `file_path` values are preserved

### Requirement: Duplicate folder link detection on submission
When a user submits a folder URL via the add form, the system SHALL check whether any existing Download already contains a top-level DownloadFile with the same normalized folder URL. If a match is found, the system SHALL warn the user and suggest re-checking the existing entry instead. The user MAY still proceed with creating a duplicate if they choose to.

#### Scenario: Duplicate folder URL detected
- **WHEN** the user submits `https://mega.nz/folder/abc#key` and an existing Download already has that folder URL
- **THEN** the system displays a warning with a link to the existing Download's detail page, offering a re-check instead

#### Scenario: Non-duplicate submission proceeds normally
- **WHEN** the user submits a folder URL that does not match any existing Download
- **THEN** the Download is created normally with no warning
