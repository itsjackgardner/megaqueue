## MODIFIED Requirements

### Requirement: Dashboard shows aggregate progress with file count
The system SHALL display aggregate progress (total bytes across all leaf files) on each download card, plus a file count indicator for downloads with multiple files showing how many files have finished. For folder downloads that have been expanded into child DownloadFile records, the count SHALL reflect the child records, not the single parent folder record.

#### Scenario: Expanded folder download shows individual file count
- **WHEN** a folder download has been split into 5 child DownloadFile records and 2 are finished
- **THEN** the dashboard card shows "2/5 files" alongside the status badge

#### Scenario: Single-file download hides file count
- **WHEN** a download has only 1 file and no children
- **THEN** no file count indicator is shown

#### Scenario: Multi-URL download shows file count
- **WHEN** a download has 3 directly-submitted file URLs, 2 of which are finished
- **THEN** the dashboard card shows "2/3 files"

### Requirement: Download detail view shows per-file breakdown
The system SHALL provide a detail view at route `/download/<id>` (GET) showing overall download metadata plus a per-file breakdown. For folder downloads with child DownloadFile records, the detail view SHALL show each child file individually (not the parent folder record). Each file entry displays its name, status badge, progress bar, bytes loaded/total, speed, error message (if any), and final file path (if organized).

#### Scenario: User views an expanded folder download in progress
- **WHEN** user navigates to the detail page for a folder download that has been split into 8 child files
- **THEN** the page shows 8 individual file entries with per-file progress, not a single folder entry

#### Scenario: User views a multi-URL download in progress
- **WHEN** user navigates to a download detail page for a download with 3 directly-submitted URLs
- **THEN** the page shows 3 individual file entries with per-file progress

#### Scenario: User views a folder download before expansion
- **WHEN** user navigates to a detail page for a folder download that megabasterd has not yet split (no child records)
- **THEN** the page shows the single folder URL entry with whatever progress is available
