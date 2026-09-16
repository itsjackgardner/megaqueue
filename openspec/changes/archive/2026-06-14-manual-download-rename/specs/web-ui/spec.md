## MODIFIED Requirements

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
The dashboard SHALL render `needs_review` Downloads with a distinct visual indicator (e.g., a coloured badge) that links to the detail view's rename form.

#### Scenario: needs_review download is visually flagged
- **WHEN** a Download enters `needs_review`
- **THEN** its dashboard card displays a "Review" badge and clicking the card opens the detail view scrolled to the rename form

## REMOVED Requirements

### Requirement: Detail view exposes a resolve form for needs_review downloads
_Replaced by the rename form requirement above, which covers `needs_review` as one of the active statuses._
