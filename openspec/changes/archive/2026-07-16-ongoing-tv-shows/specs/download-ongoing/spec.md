## ADDED Requirements

### Requirement: User can mark downloads as ongoing or finished
The system SHALL allow the user to toggle an `ongoing` flag on any Download, regardless of its current status. Marking as ongoing and marking as finished SHALL be available from both the dashboard and the detail page.

#### Scenario: User marks a completed download as ongoing
- **WHEN** the user clicks the "Mark as ongoing" action on a completed Download
- **THEN** the Download's `ongoing` field is set to `true` and the download appears in the Ongoing section

#### Scenario: User marks a download as finished
- **WHEN** the user clicks the "Mark as finished" action on an ongoing Download
- **THEN** the Download's `ongoing` field is set to `false` and the download moves back to the main list

#### Scenario: Ongoing persists across status changes
- **WHEN** an ongoing Download transitions from `complete` to `downloading` (via re-check)
- **THEN** the `ongoing` flag remains `true`

### Requirement: Dashboard has an Ongoing section
The dashboard SHALL render an "Ongoing" section at the top of the page, above the main download list, when at least one Download has `ongoing=true`. The Ongoing section SHALL display ongoing downloads in the same card format as the main list. When no downloads are ongoing, the Ongoing section SHALL NOT be rendered.

#### Scenario: Ongoing section appears with ongoing downloads
- **WHEN** 2 Downloads have `ongoing=true` and 5 have `ongoing=false`
- **THEN** the dashboard shows an "Ongoing" section with the 2 ongoing downloads, followed by the main list with the 5 non-ongoing downloads

#### Scenario: Ongoing section hidden when empty
- **WHEN** no Downloads have `ongoing=true`
- **THEN** the dashboard does not render the Ongoing section at all

#### Scenario: Ongoing downloads excluded from main list
- **WHEN** a Download has `ongoing=true`
- **THEN** it appears only in the Ongoing section, not duplicated in the main list below
