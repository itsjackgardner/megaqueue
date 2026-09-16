## ADDED Requirements

### Requirement: System sends push notification on download completion
The system SHALL send an HTTP POST to the configured ntfy.sh server/topic when a download status transitions to "complete".

#### Scenario: Completion notification is sent
- **WHEN** a download with title "Inception" and year 2010 completes successfully
- **THEN** a POST request is sent to `<NTFY_SERVER>/<NTFY_TOPIC>` with title "Download Complete" and message "Inception (2010) is ready in Plex"

### Requirement: System sends push notification on download failure
The system SHALL send an HTTP POST to the configured ntfy.sh server/topic when a download status transitions to "failed".

#### Scenario: Failure notification is sent
- **WHEN** a download with title "Inception" fails with error "Link not found"
- **THEN** a POST request is sent to `<NTFY_SERVER>/<NTFY_TOPIC>` with title "Download Failed" and message including "Inception" and the error reason

### Requirement: Notification failures do not block the worker
The system SHALL catch and log notification delivery failures without affecting the download worker's operation.

#### Scenario: ntfy.sh is unreachable
- **WHEN** a download completes but the ntfy.sh POST request fails (network error, timeout)
- **THEN** the error is logged, the download remains in "complete" status, and the worker continues processing the next queued download
