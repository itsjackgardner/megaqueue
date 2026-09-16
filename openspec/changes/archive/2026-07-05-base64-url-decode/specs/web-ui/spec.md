## MODIFIED Requirements

### Requirement: Add download form accepts only mega.nz links
The system SHALL provide a form at route `/download` (POST) accepting only mega.nz links (one per line in a textarea). Each submitted line SHALL be passed through `maybe_decode_base64()` before validation, allowing base64-encoded (and double-encoded) mega.nz URLs to be submitted directly. The form SHALL NOT ask for title, year, or media_type — those are inferred by the metadata-resolution capability from the resolved file names. The form SHALL include CSRF protection.

#### Scenario: User submits one or more links
- **WHEN** user pastes one or more mega.nz links (one per line) and submits
- **THEN** a single new Download is created with `title=null`, `year=null`, `media_type=null`, `status="queued"`, one DownloadFile per link, and the user is redirected to the dashboard

#### Scenario: User submits a folder link
- **WHEN** user pastes `https://mega.nz/folder/abc#key` and submits
- **THEN** a Download is created with one DownloadFile (the folder URL), submitted to megabasterd, and after megabasterd resolves the folder the child records are populated and guessit runs

#### Scenario: User submits a base64-encoded link
- **WHEN** user pastes a base64-encoded mega.nz URL and submits
- **THEN** the system decodes it and creates a DownloadFile with the decoded mega.nz URL

#### Scenario: User submits a double-encoded link
- **WHEN** user pastes a double-base64-encoded mega.nz URL and submits
- **THEN** the system decodes both layers and creates a DownloadFile with the decoded mega.nz URL

#### Scenario: User submits a mix of raw and encoded links
- **WHEN** user pastes three lines — one raw mega.nz URL, one base64-encoded URL, and one double-encoded URL
- **THEN** all three are decoded/passed-through and stored as valid mega.nz URLs in the created Download
