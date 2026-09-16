## MODIFIED Requirements

### Requirement: Add download form accepts only mega.nz links
The system SHALL provide a form at route `/download` (POST) accepting only mega.nz links (one per line in a textarea). The form SHALL NOT ask for title, year, or media_type — those are inferred by the metadata-resolution capability from the resolved file names. The form SHALL include CSRF protection.

#### Scenario: User submits one or more links
- **WHEN** user pastes one or more mega.nz links (one per line) and submits
- **THEN** a single new Download is created with `title=null`, `year=null`, `media_type=null`, `status="queued"`, one DownloadFile per link, and the user is redirected to the dashboard

#### Scenario: User submits a folder link
- **WHEN** user pastes `https://mega.nz/folder/abc#key` and submits
- **THEN** a Download is created with one DownloadFile (the folder URL), submitted to megabasterd, and after megabasterd resolves the folder the child records are populated and guessit runs

### Requirement: Dashboard reflects metadata as it resolves
The dashboard SHALL render each Download with its currently-known metadata. Downloads with `title=null` SHALL display a "Resolving…" placeholder. Once `title` is populated (by guessit on the first poll tick after a file name lands), the dashboard SHALL display the resolved title on the next poll cycle without requiring a page reload.

#### Scenario: Newly submitted download shows resolving placeholder
- **WHEN** a Download was just submitted and no file names have been reported by megabasterd
- **THEN** its dashboard card shows "Resolving…" in place of the title

#### Scenario: Title appears once guessit has run
- **WHEN** megabasterd reports a file name and guessit aggregates it into the Download's title field
- **THEN** the dashboard card swaps "Resolving…" for the resolved title on the next 5-second poll tick

## ADDED Requirements

### Requirement: Detail view exposes a resolve form for needs_review downloads
The download detail view SHALL render an inline resolve form when `Download.status == "needs_review"`. The form SHALL allow the user to set `title`, `year`, `media_type`, and per-leaf-file `is_extra` toggles. Submitting the form to `POST /download/<id>/resolve` SHALL write the values with `metadata_source="user"`, `metadata_confidence="high"`, and transition the Download to `processing`. The form SHALL include CSRF protection.

#### Scenario: User resolves a low-confidence movie
- **WHEN** a Download is in `needs_review` because no year was detected, the user enters `year=2004` and submits
- **THEN** the Download writes `year=2004`, `metadata_source="user"`, `metadata_confidence="high"`, transitions to `processing`, and the worker runs the organiser on the next tick

#### Scenario: User tags featurettes manually
- **WHEN** the user toggles `is_extra=true` on three child files and submits
- **THEN** those three records are updated, the Download moves to `processing`, and the organiser places those files into `Featurettes/`

#### Scenario: Resolve form is hidden for high-confidence downloads
- **WHEN** the detail view is rendered for a Download with `metadata_confidence="high"`
- **THEN** the resolve form is not rendered

### Requirement: Dashboard surfaces needs_review state
The dashboard SHALL render `needs_review` Downloads with a distinct visual indicator (e.g., a coloured badge) that links to the detail view's resolve form.

#### Scenario: needs_review download is visually flagged
- **WHEN** a Download enters `needs_review`
- **THEN** its dashboard card displays a "Review" badge and clicking the card opens the detail view scrolled to the resolve form
