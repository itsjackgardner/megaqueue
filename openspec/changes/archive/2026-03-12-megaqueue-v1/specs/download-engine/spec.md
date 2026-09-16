## ADDED Requirements

### Requirement: Flask routes submit downloads to megabasterd
The system SHALL submit mega.nz links to megabasterd immediately when a download is created or retried, by sending a POST request to megabasterd's `/start` endpoint. The download status is set to "queued" and downloading_since is stamped on successful submission.

#### Scenario: New download is submitted on creation
- **WHEN** a user adds a download with 3 mega.nz links
- **THEN** the Flask route POSTs all 3 links to megabasterd's `/start` endpoint and creates the download with status "queued"

#### Scenario: Submission failure marks download as failed
- **WHEN** a user adds a download but megabasterd is unreachable
- **THEN** the download is created with status "failed" and an error message indicating the submission failure

#### Scenario: Retry re-submits to megabasterd
- **WHEN** a user retries a failed download
- **THEN** the Flask route re-submits the links to megabasterd, resets all file statuses to "queued", and sets the download status to "queued"

### Requirement: Worker polls megabasterd status on a fixed interval
The system SHALL run a background worker thread that polls megabasterd's `GET /status` endpoint on a configurable interval (default 5 seconds) and uses the response to update all active downloads.

#### Scenario: Worker fetches status each tick
- **WHEN** the poll interval elapses
- **THEN** the worker makes a single GET request to `/status` and processes all downloads in the response

#### Scenario: Poll failure is logged and retried
- **WHEN** the GET `/status` request fails
- **THEN** the error is logged and the worker retries on the next tick

### Requirement: Worker updates per-file progress from megabasterd status
The system SHALL match each megabasterd download entry to a DownloadFile record by normalized mega.nz URL and update that file's progress_bytes, total_bytes, speed, name, and status.

#### Scenario: File progress is updated
- **WHEN** megabasterd reports a file at 500MB of 1.2GB with speed 5MB/s
- **THEN** the matching DownloadFile's progress_bytes, total_bytes, and speed are updated

#### Scenario: File name is populated from megabasterd
- **WHEN** megabasterd reports a download with name "Movie.2024.1080p.mkv"
- **THEN** the matching DownloadFile's name field is set to that value

### Requirement: Worker normalizes mega.nz URLs for matching
The system SHALL normalize mega.nz URLs before matching, handling both old format (`https://mega.nz/#!{id}!{key}`) and new format (`https://mega.nz/file/{id}#{key}`) by extracting the file ID and key.

#### Scenario: Old and new URL formats match
- **WHEN** megaqueue stores `https://mega.nz/file/abc#xyz` and megabasterd returns `https://mega.nz/#!abc!xyz`
- **THEN** the worker correctly matches them as the same file

### Requirement: Worker detects file completion and triggers post-processing
The system SHALL detect that all files in a download have finished by checking `finished: true` on each matched megabasterd entry. When all files are finished, the download transitions to "processing" and post-processing is triggered.

#### Scenario: All files complete
- **WHEN** megabasterd reports `finished: true` for all files in a download
- **THEN** the download status transitions to "processing" and file organization begins

#### Scenario: Finished downloads are cleared from megabasterd
- **WHEN** post-processing completes for a download
- **THEN** the worker calls `POST /stop` for each file's URL to remove them from megabasterd

### Requirement: Worker detects and reports megabasterd errors
The system SHALL detect download failures by checking for error statuses in megabasterd's `/status` response, including "Error" and "509 Bandwidth Limit Exceeded".

#### Scenario: File fails with error
- **WHEN** megabasterd reports status "Error" for a file
- **THEN** the DownloadFile status is set to "failed" with the error message from megabasterd

#### Scenario: Bandwidth limit exceeded (non-terminal)
- **WHEN** megabasterd reports "509 Bandwidth Limit Exceeded" for a file
- **THEN** the DownloadFile's error_message is updated but status remains unchanged

### Requirement: Worker performs integrity sweep for stuck records
The system SHALL check all active downloads after processing megabasterd results. Any DownloadFile in "queued" or "downloading" status that was not matched in megabasterd and whose parent download's downloading_since exceeds the grace period (configurable, default 30 seconds) SHALL be marked as failed.

#### Scenario: Download disappears from megabasterd after grace period
- **WHEN** a file has been in "downloading" status for over 30 seconds but is no longer in megabasterd's status
- **THEN** the file is marked "failed" with message "Disappeared from megabasterd"

#### Scenario: Recently submitted download is not prematurely failed
- **WHEN** a download was submitted 5 seconds ago and hasn't appeared in megabasterd yet
- **THEN** the worker does not mark it as failed (within grace period)

### Requirement: Flask route handles cancellation directly
The system SHALL cancel downloads by setting the status to "cancelled" in the database and calling `POST /stop` on megabasterd for each file's URL directly from the Flask route.

#### Scenario: User cancels a downloading item
- **WHEN** a user cancels a download
- **THEN** the Flask route sets status to "cancelled" and sends stop requests to megabasterd for all files

### Requirement: Worker can clear 509 errors via megabasterd API
The system SHALL provide a mechanism to clear 509 bandwidth limit errors by sending a POST to megabasterd's `/clear509` endpoint.

#### Scenario: User clears 509 errors
- **WHEN** a download has 509 errors and the user clicks "Clear 509"
- **THEN** a POST is sent to `/clear509` and megabasterd restarts affected workers

### Requirement: Startup validates megabasterd API is reachable
The system SHALL verify at startup that megabasterd's REST API is reachable by sending a GET request to `/status`. If the API is unreachable, the application logs a clear error message.

#### Scenario: Megabasterd API is unreachable
- **WHEN** the GET `/status` request fails (connection refused, timeout)
- **THEN** the application logs "Megabasterd API not reachable at http://localhost:<port> — is megabasterd running with the API enabled?"
