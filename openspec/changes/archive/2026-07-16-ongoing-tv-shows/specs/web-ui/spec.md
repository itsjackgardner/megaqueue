## ADDED Requirements

### Requirement: Dashboard displays Ongoing section
The dashboard SHALL render an "Ongoing" section at the top of the page when at least one Download has `ongoing=true`. Ongoing downloads SHALL use the same card format as the main list. When no downloads are ongoing, the section SHALL NOT be rendered. Ongoing downloads SHALL NOT appear in the main list below.

#### Scenario: Ongoing section rendered
- **WHEN** the dashboard loads and 2 Downloads have `ongoing=true`
- **THEN** an "Ongoing" section appears at the top with those 2 downloads, and they do not appear in the main list

#### Scenario: No ongoing downloads
- **WHEN** no Downloads have `ongoing=true`
- **THEN** the Ongoing section is not rendered

### Requirement: Ongoing toggle on dashboard and detail page
The dashboard cards and the detail page SHALL include an ongoing toggle button. For non-ongoing downloads, it SHALL display "Mark as ongoing". For ongoing downloads, it SHALL display "Mark as finished". The toggle SHALL send a POST request to `/download/<id>/ongoing` which flips the `ongoing` flag. After toggling, the page SHALL reload to reflect the change.

#### Scenario: Mark as ongoing from dashboard
- **WHEN** the user clicks "Mark as ongoing" on a download's dashboard card
- **THEN** a POST is sent to `/download/<id>/ongoing`, the download becomes ongoing, and the page reloads showing it in the Ongoing section

#### Scenario: Mark as finished from detail page
- **WHEN** the user clicks "Mark as finished" on an ongoing download's detail page
- **THEN** the download becomes non-ongoing and the page reloads

### Requirement: Re-check button on detail page for completed folder downloads
The detail page SHALL render a "Re-check for new files" button when the Download's status is `complete` AND the Download has at least one top-level DownloadFile with a folder URL. The button SHALL send a POST request to `/download/<id>/recheck`. The button SHALL NOT appear for non-complete downloads or downloads without folder URLs.

#### Scenario: Re-check button shown for completed folder download
- **WHEN** the detail page loads for a `complete` Download with a folder URL
- **THEN** a "Re-check for new files" button is visible

#### Scenario: Re-check button hidden for single-file download
- **WHEN** the detail page loads for a `complete` Download with only single-file URLs
- **THEN** no re-check button is rendered

#### Scenario: Re-check button hidden for active download
- **WHEN** the detail page loads for a `downloading` Download with a folder URL
- **THEN** no re-check button is rendered

### Requirement: Add form warns on duplicate folder URLs
The add form (`POST /download`) SHALL check submitted folder URLs against existing Downloads' top-level DownloadFile URLs. If a match is found, the system SHALL render the add page with a warning message that includes a link to the existing Download's detail page and suggests using re-check. The user SHALL be able to dismiss the warning and submit anyway via a confirmation mechanism.

#### Scenario: Duplicate detected and warning shown
- **WHEN** the user submits `https://mega.nz/folder/abc#key` and an existing Download has that URL
- **THEN** the add page re-renders with a warning: "This folder is already in your queue" with a link to the existing download, and an option to submit anyway

#### Scenario: User confirms duplicate submission
- **WHEN** the user sees the duplicate warning and confirms they want to proceed
- **THEN** the Download is created normally

#### Scenario: No duplicate, normal flow
- **WHEN** the user submits a folder URL not found in existing Downloads
- **THEN** the Download is created with no warning

### Requirement: Re-check result feedback
After a re-check completes, the detail page SHALL display a flash message indicating the result: either the number of new files found and queued, or that no new files were found.

#### Scenario: New files found
- **WHEN** a re-check finds 3 new files
- **THEN** the detail page shows a message like "Found 3 new files — downloading"

#### Scenario: No new files found
- **WHEN** a re-check finds no new files
- **THEN** the detail page shows a message like "No new files found"
