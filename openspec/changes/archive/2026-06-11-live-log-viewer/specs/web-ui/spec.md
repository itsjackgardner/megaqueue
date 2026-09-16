## ADDED Requirements

### Requirement: Navigation includes a logs page link
The base template SHALL include a navigation link to `/logs` as a proper nav item, visible on all pages. The link SHALL be visually consistent with the existing navigation style.

#### Scenario: Logs link is visible from the dashboard
- **WHEN** the user is on the dashboard (`/`)
- **THEN** a "Logs" navigation link is visible that navigates to `/logs`

#### Scenario: Logs link is visible from the detail page
- **WHEN** the user is on a download detail page (`/download/<id>`)
- **THEN** the same "Logs" navigation link is visible
