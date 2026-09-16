## ADDED Requirements

### Requirement: Dashboard displays all downloads grouped by status
The system SHALL display a dashboard at route `/` showing all downloads as cards, sorted with downloading first, then queued, then recent completions.

#### Scenario: Dashboard shows active and completed downloads
- **WHEN** a user visits the dashboard with 1 downloading, 2 queued, and 3 completed downloads
- **THEN** the page displays 6 cards ordered: downloading first, queued second, completed last, each showing title, status badge, and progress info

### Requirement: Dashboard shows aggregate progress with file count
The system SHALL display aggregate progress (total bytes across all files) on each download card, plus a file count indicator (e.g., "2/3 files") for multi-file downloads showing how many files have finished.

#### Scenario: Multi-file download shows file count
- **WHEN** a download has 3 files, 2 of which are finished
- **THEN** the dashboard card shows "2/3 files" alongside the status badge

#### Scenario: Single-file download hides file count
- **WHEN** a download has only 1 file
- **THEN** no file count indicator is shown

### Requirement: Add download form accepts title, year, type, and links
The system SHALL provide a form at route `/download` (POST) accepting: title (required text), year (optional integer), media_type (movie or tv toggle), and mega.nz links (one per line in a textarea). The form SHALL include CSRF protection.

#### Scenario: User submits a valid movie download
- **WHEN** user submits title "Inception", year 2010, type "movie", and one mega.nz link
- **THEN** a new download is created with status "queued", submitted to megabasterd, and user is redirected to the dashboard

#### Scenario: User submits multiple links for a multi-file download
- **WHEN** user pastes 3 mega.nz links (one per line) in the links textarea
- **THEN** 3 DownloadFile records are created, all links are submitted to megabasterd, and the download appears on the dashboard

### Requirement: Dashboard auto-refreshes via polling
The system SHALL auto-refresh download status on the dashboard every 5 seconds by fetching `/api/status` (JSON endpoint) and updating the DOM without full page reload.

#### Scenario: Download progress updates in real time
- **WHEN** a download is in "downloading" status and progress grows from 300MB to 500MB
- **THEN** the dashboard reflects the updated progress within 5 seconds without user interaction

### Requirement: Download detail view shows per-file breakdown
The system SHALL provide a detail view at route `/download/<id>` (GET) showing overall download metadata plus a per-file breakdown. Each file displays its name (from megabasterd) or URL, status badge, progress bar, bytes loaded/total, speed, error message (if any), and final file path (if organized).

#### Scenario: User views an active multi-file download
- **WHEN** user navigates to a download detail page for a download with 3 files
- **THEN** the page shows overall aggregate progress at the top and individual file progress for each of the 3 files

#### Scenario: User views a failed download
- **WHEN** user navigates to a download detail page for a failed download
- **THEN** the page shows per-file error messages explaining which files failed and why

### Requirement: User can retry a failed download
The system SHALL allow retrying a failed or cancelled download via POST to `/download/<id>/retry`, which re-submits links to megabasterd and resets all file statuses to "queued".

#### Scenario: Retry requeues the download
- **WHEN** user clicks retry on a failed download
- **THEN** the download is re-submitted to megabasterd, all files are reset to "queued", and the download re-enters the processing queue

### Requirement: User can delete a download
The system SHALL allow deleting a download via POST to `/download/<id>/delete`, removing it and all associated file records from the database.

#### Scenario: Delete removes a download and its files
- **WHEN** user deletes a download with 3 files
- **THEN** the download and all 3 DownloadFile records are removed from the database

### Requirement: UI is mobile-first
The system SHALL render a mobile-optimized layout using Tailwind CSS that is usable on phone-sized screens without horizontal scrolling.

#### Scenario: Phone browser displays usable interface
- **WHEN** user accesses the app from a phone browser
- **THEN** all UI elements (forms, buttons, cards, per-file progress) are properly sized and accessible for touch interaction

### Requirement: All state-changing forms include CSRF protection
The system SHALL include a CSRF token in all POST forms to prevent cross-site request forgery attacks.

#### Scenario: Request without valid CSRF token is rejected
- **WHEN** a POST request is made to `/download` without a valid CSRF token
- **THEN** the request is rejected with a 400 error
