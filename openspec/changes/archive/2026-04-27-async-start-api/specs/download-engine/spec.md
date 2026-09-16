## ADDED Requirements

### Requirement: Megabasterd /start endpoint is asynchronous
The megabasterd `/start` endpoint SHALL accept URLs, add them to an in-memory pending queue, and return immediately with a JSON response containing the queued URL count and the raw URLs. Link resolution (including folder enumeration via `FolderLinkDialog`) and download creation SHALL happen asynchronously in a background thread.

#### Scenario: Single file URL submitted
- **WHEN** a client POSTs `{"urls": "https://mega.nz/file/abc#xyz"}` to `/start`
- **THEN** the endpoint returns within 1 second with `{"message": "1 links queued", "urls": ["https://mega.nz/file/abc#xyz"]}`
- **AND** the download is created asynchronously and appears in `/status` once processing completes

#### Scenario: Folder URL submitted
- **WHEN** a client POSTs a folder URL `https://mega.nz/folder/abc#xyz` to `/start`
- **THEN** the endpoint returns within 1 second with the folder URL in the response
- **AND** the background thread resolves the folder into per-file downloads asynchronously

#### Scenario: Multiple URLs submitted
- **WHEN** a client POSTs 5 URLs (mix of file and folder) to `/start`
- **THEN** all 5 are queued and the response includes all 5 URLs

### Requirement: Megabasterd /status includes pending entries
The megabasterd `/status` endpoint SHALL include entries for URLs that have been submitted via `/start` but have not yet been resolved into active downloads. Pending entries SHALL have `status: "Pending"`, `finished: false`, `bytesLoaded: 0`, `bytesTotal: 0`, `speed: 0`, and the original submitted URL. Once the background thread resolves and starts the download, the pending entry SHALL be replaced by the normal download entry (or entries, for folder splits).

#### Scenario: URL is pending resolution
- **WHEN** a folder URL was submitted to `/start` 5 seconds ago and is still being resolved
- **THEN** `/status` includes an entry with `url` set to the folder URL, `status: "Pending"`, and `finished: false`

#### Scenario: URL finishes resolution
- **WHEN** a pending folder URL resolves into 3 per-file downloads
- **THEN** the pending entry is removed from `/status` and replaced by 3 download entries with their respective per-file URLs

#### Scenario: Single file URL pending briefly
- **WHEN** a single file URL is submitted and queued
- **THEN** it appears as pending until the `Download` object is created and added to the download manager

### Requirement: Megabasterd /status includes sourceUrl for folder-split entries
When megabasterd creates per-file downloads from a folder URL, each download entry in the `/status` response SHALL include a `sourceUrl` field set to the original folder URL that was submitted. Single-file downloads (not from folder splits) SHALL omit `sourceUrl` or set it to `null`.

#### Scenario: Folder split entries include sourceUrl
- **WHEN** folder URL `https://mega.nz/folder/abc#xyz` is resolved into 3 per-file downloads
- **THEN** each of the 3 entries in `/status` includes `sourceUrl: "https://mega.nz/folder/abc#xyz"`

#### Scenario: Single file download has no sourceUrl
- **WHEN** a single file URL `https://mega.nz/file/def#key` is downloaded
- **THEN** its `/status` entry does not include `sourceUrl` (or it is `null`)

### Requirement: Worker submits to megabasterd synchronously (fast path)
The megaqueue worker SHALL submit pending downloads (status "queued", `downloading_since` is NULL) to megabasterd by calling `POST /start` synchronously during each poll tick. Since the megabasterd `/start` endpoint is now asynchronous, this call returns immediately and does not block the worker loop. On success, the worker SHALL stamp `downloading_since` to the current time. On failure, the worker SHALL mark the download as failed with the error message.

#### Scenario: Worker submits a queued download
- **WHEN** the worker finds a download with status "queued" and `downloading_since=None`
- **THEN** it calls `POST /start` with the download's links, and on success stamps `downloading_since`

#### Scenario: Submission fails
- **WHEN** `POST /start` returns an error or times out
- **THEN** the download status is set to "failed" with the error message

#### Scenario: Already-submitted downloads are not re-submitted
- **WHEN** a download has status "queued" and `downloading_since` is set (already submitted)
- **THEN** the worker does not call `/start` again

### Requirement: Worker matches folder-split entries via sourceUrl
The megaqueue worker SHALL use the `sourceUrl` field from megabasterd `/status` entries as the primary method for matching folder-split downloads to `DownloadFile` records (Tier 2). When `sourceUrl` is present and matches a `DownloadFile` URL after normalization, the entry is matched to that record. The existing Tier 3 folder-ID matching SHALL remain as a fallback for backward compatibility.

#### Scenario: Folder-split matched by sourceUrl
- **WHEN** megabasterd returns 3 entries each with `sourceUrl: "https://mega.nz/folder/abc#xyz"`
- **AND** a `DownloadFile` exists with URL `https://mega.nz/folder/abc#xyz`
- **THEN** all 3 entries are matched to that `DownloadFile` via Tier 2

#### Scenario: Fallback to folder-ID matching when sourceUrl is absent
- **WHEN** megabasterd returns entries without `sourceUrl` (old API version)
- **THEN** the worker falls back to Tier 3 folder-ID extraction matching

### Requirement: Worker matches pending entries from megabasterd status
The megaqueue worker SHALL match megabasterd `/status` entries with `status: "Pending"` to `DownloadFile` records using the same URL matching logic. Pending entries SHALL keep the `DownloadFile` status as "queued" and SHALL count as matched (preventing the integrity sweep from failing them).

#### Scenario: Pending entry prevents integrity sweep failure
- **WHEN** a download was submitted 45 seconds ago and megabasterd shows the URL as "Pending"
- **THEN** the `DownloadFile` is matched and the integrity sweep does not mark it as failed

#### Scenario: Pending entry does not advance status
- **WHEN** megabasterd shows a URL as "Pending" with `bytesLoaded: 0`
- **THEN** the `DownloadFile` remains in "queued" status

## MODIFIED Requirements

### Requirement: Worker performs integrity sweep for stuck records
The system SHALL check all active downloads after processing megabasterd results. Any DownloadFile in "queued" or "downloading" status that was not matched in megabasterd and whose parent download's downloading_since exceeds the grace period (configurable, default 30 seconds) SHALL be marked as failed. Downloads with `downloading_since=None` (not yet submitted to megabasterd) SHALL be excluded from the integrity sweep entirely.

#### Scenario: Download disappears from megabasterd after grace period
- **WHEN** a file has been in "downloading" status for over 30 seconds but is no longer in megabasterd's status
- **THEN** the file is marked "failed" with message "Disappeared from megabasterd"

#### Scenario: Recently submitted download is not prematurely failed
- **WHEN** a download was submitted 5 seconds ago and hasn't appeared in megabasterd yet
- **THEN** the worker does not mark it as failed (within grace period)

#### Scenario: Unsubmitted download is excluded from integrity sweep
- **WHEN** a download has status "queued" and `downloading_since` is NULL
- **THEN** the integrity sweep skips it entirely

## REMOVED Requirements

### Requirement: Flask routes submit downloads to megabasterd
**Reason**: Replaced by worker-driven submission. Routes now save downloads as queued with `downloading_since=None`; the worker submits to megabasterd on the next poll tick. This eliminates HTTP timeouts in the user-facing request.
**Migration**: No action needed — the route already saves to DB without calling megabasterd (implemented in prior commit). The worker's `_submit_pending_downloads` replaces the route's direct call.
