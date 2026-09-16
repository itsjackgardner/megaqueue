## ADDED Requirements

### Requirement: Detail view progress bars update live
The download detail page SHALL poll `/api/status` every 5 seconds when the download's status is `downloading` or `queued`. On each poll tick, the overall progress bar and per-file progress bars SHALL update their width, byte counts, percentage, and speed without a full page reload. If the download's status changes between ticks (e.g., `downloading` → `complete`), the page SHALL perform a full reload to reflect the new state. If `total_bytes` appears for the first time (progress bars not yet rendered), the page SHALL perform a full reload to render them. The polling mechanism and visual behavior SHALL match the dashboard's existing live-refresh pattern (`static/refresh.js`).

#### Scenario: User watches a download in progress on the detail page
- **WHEN** a user is viewing the detail page for a `downloading` Download
- **THEN** the overall progress bar and per-file progress bars update every 5 seconds with current progress, speed, and percentage — without requiring a manual page refresh

#### Scenario: Download completes while user is on the detail page
- **WHEN** a Download transitions from `downloading` to `complete` while the user is viewing its detail page
- **THEN** the page automatically reloads to show the completed state

#### Scenario: File starts downloading while user is on the detail page
- **WHEN** a file within the download starts downloading and `total_bytes` becomes available for the first time
- **THEN** the page automatically reloads to render the newly available progress bar
