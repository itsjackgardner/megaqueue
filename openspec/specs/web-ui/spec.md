## MODIFIED Requirements

### Requirement: Add download form accepts only mega.nz links
The system SHALL provide a form at route `/download` (POST) accepting only mega.nz links (one per line in a textarea). Each submitted line SHALL be passed through `maybe_decode_base64()` before validation, allowing base64-encoded (and double-encoded) mega.nz URLs to be submitted directly. The form SHALL NOT ask for title, year, or media_type — those are inferred by the metadata-resolution capability from the resolved file names. The form SHALL include CSRF protection.

#### Scenario: User submits one or more links
- **WHEN** user pastes one or more mega.nz links (one per line) and submits
- **THEN** a single new Download is created with `title=null`, `year=null`, `media_type=null`, `status="queued"`, one DownloadFile per link, and the user is redirected to the dashboard

#### Scenario: User submits a folder link
- **WHEN** user pastes `https://mega.nz/folder/abc#key` and submits
- **THEN** a Download is created with one DownloadFile (the folder URL), submitted to the download manager, and after the folder is resolved the child records are populated and guessit runs

#### Scenario: User submits a base64-encoded link
- **WHEN** user pastes a base64-encoded mega.nz URL and submits
- **THEN** the system decodes it and creates a DownloadFile with the decoded mega.nz URL

#### Scenario: User submits a double-encoded link
- **WHEN** user pastes a double-base64-encoded mega.nz URL and submits
- **THEN** the system decodes both layers and creates a DownloadFile with the decoded mega.nz URL

#### Scenario: User submits a mix of raw and encoded links
- **WHEN** user pastes three lines — one raw mega.nz URL, one base64-encoded URL, and one double-encoded URL
- **THEN** all three are decoded/passed-through and stored as valid mega.nz URLs in the created Download

### Requirement: Dashboard reflects metadata as it resolves
The dashboard SHALL render each Download with its currently-known metadata. Downloads with `title=null` SHALL display a "Resolving…" placeholder. Once `title` is populated (by guessit on the first poll tick after a file name lands), the dashboard SHALL display the resolved title on the next poll cycle without requiring a page reload.

#### Scenario: Newly submitted download shows resolving placeholder
- **WHEN** a Download was just submitted and no file names have been reported by the download manager
- **THEN** its dashboard card shows "Resolving…" in place of the title

#### Scenario: Title appears once guessit has run
- **WHEN** the download manager reports a file name and guessit aggregates it into the Download's title field
- **THEN** the dashboard card swaps "Resolving…" for the resolved title on the next 5-second poll tick

## ADDED Requirements

### Requirement: Detail view exposes a rename form for active downloads
The download detail view SHALL render a rename form when `Download.status` is one of `queued`, `downloading`, or `needs_review`. The form SHALL allow the user to set `title`, `year`, `media_type`, and per-leaf-file `is_extra` toggles. Submitting the form to `POST /download/<id>/rename` SHALL write the values with `metadata_source="user"`, `metadata_confidence="high"`. For `needs_review` downloads, it SHALL also transition the status to `downloading` so the worker can re-derive. For `queued` and `downloading` downloads, the status SHALL remain unchanged. The form SHALL include CSRF protection. The form SHALL NOT be rendered for `processing`, `complete`, `failed`, or `cancelled` downloads.

#### Scenario: User renames a downloading download
- **WHEN** a Download is actively downloading with guessit-resolved `title="Birth"`, `year=2004`, and the user submits the rename form with `title="Rebirth"`, `year=2004`
- **THEN** the Download writes `title="Rebirth"`, `metadata_source="user"`, `metadata_confidence="high"`, status remains `downloading`, and subsequent guessit runs do not overwrite the title

#### Scenario: User resolves a low-confidence download via rename
- **WHEN** a Download is in `needs_review` and the user submits the rename form with `title="Birth"`, `year=2004`, `media_type="movie"`
- **THEN** the Download writes those values, `metadata_source="user"`, `metadata_confidence="high"`, transitions to `downloading`, and the worker picks it up on the next tick

#### Scenario: User tags featurettes via rename
- **WHEN** the user toggles `is_extra=true` on three child files via the rename form
- **THEN** those three records are updated and the organiser (when it eventually runs) places those files into `Featurettes/`

#### Scenario: Rename form is hidden for terminal downloads
- **WHEN** the detail view is rendered for a Download with status `complete`, `failed`, or `cancelled`
- **THEN** the rename form is not rendered

#### Scenario: Rename form collapsed for confident downloads
- **WHEN** the detail view is rendered for a `downloading` Download with `metadata_confidence="high"`
- **THEN** the rename form is available but collapsed behind an "Edit details" button, not expanded by default

#### Scenario: Rename form expanded for needs_review
- **WHEN** the detail view is rendered for a `needs_review` Download
- **THEN** the rename form is expanded and visually prominent (same as the previous resolve form)

### Requirement: Dashboard surfaces needs_review state
The dashboard SHALL render `needs_review` Downloads with a distinct visual indicator (e.g., a coloured badge) that links to the detail view's resolve form.

#### Scenario: needs_review download is visually flagged
- **WHEN** a Download enters `needs_review`
- **THEN** its dashboard card displays a "Review" badge and clicking the card opens the detail view scrolled to the rename form

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

### Requirement: Navigation includes a logs page link
The base template SHALL include a navigation link to `/logs` as a proper nav item, visible on all pages. The link SHALL be visually consistent with the existing navigation style.

#### Scenario: Logs link is visible from the dashboard
- **WHEN** the user is on the dashboard (`/`)
- **THEN** a "Logs" navigation link is visible that navigates to `/logs`

#### Scenario: Logs link is visible from the detail page
- **WHEN** the user is on a download detail page (`/download/<id>`)
- **THEN** the same "Logs" navigation link is visible

### Requirement: Dashboard displays Ongoing section
The dashboard SHALL render an "Ongoing" section at the top of the page when at least one Download has `ongoing=true`. Ongoing downloads SHALL use the same card format as the main list, rendered inside a visually distinct bordered container. When no downloads are ongoing, the section SHALL NOT be rendered. Ongoing downloads SHALL NOT appear in the main list below.

#### Scenario: Ongoing section rendered
- **WHEN** the dashboard loads and 2 Downloads have `ongoing=true`
- **THEN** an "Ongoing" section appears at the top with those 2 downloads, and they do not appear in the main list

#### Scenario: No ongoing downloads
- **WHEN** no Downloads have `ongoing=true`
- **THEN** the Ongoing section is not rendered

### Requirement: Ongoing toggle on detail page
The detail page SHALL include an ongoing toggle button. For non-ongoing downloads, it SHALL display "Mark as ongoing". For ongoing downloads, it SHALL display "Mark as finished". The toggle SHALL send a POST request to `/download/<id>/ongoing` which flips the `ongoing` flag.

#### Scenario: Mark as ongoing from detail page
- **WHEN** the user clicks "Mark as ongoing" on a download's detail page
- **THEN** a POST is sent to `/download/<id>/ongoing`, the download becomes ongoing

#### Scenario: Mark as finished from detail page
- **WHEN** the user clicks "Mark as finished" on an ongoing download's detail page
- **THEN** the download becomes non-ongoing

### Requirement: Re-check button on detail page for ongoing completed folder downloads
The detail page SHALL render a "Re-check for new files" button when the Download is marked as ongoing, has status `complete`, AND has at least one top-level DownloadFile with a folder URL. The button SHALL send a POST request to `/download/<id>/recheck`. The button SHALL NOT appear for non-ongoing, non-complete, or non-folder downloads.

#### Scenario: Re-check button shown for ongoing completed folder download
- **WHEN** the detail page loads for an ongoing `complete` Download with a folder URL
- **THEN** a "Re-check for new files" button is visible

#### Scenario: Re-check button hidden for non-ongoing completed folder download
- **WHEN** the detail page loads for a non-ongoing `complete` Download with a folder URL
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
