## ADDED Requirements

### Requirement: System sends push notification when a download needs review
The system SHALL send an ntfy.sh push notification when a Download transitions to `needs_review`. The notification SHALL include: the Download's currently-known title (or "(unresolved)" if `title` is null), a short reason listing what guessit could not determine (e.g., "no year detected", "mixed file types", "no S/E pattern"), and a deep link to the detail view's resolve form.

#### Scenario: needs_review notification on movie without year
- **WHEN** a movie Download with `title="Movie"` transitions to `needs_review` because no file had a year
- **THEN** an ntfy push fires with title "Review needed: Movie", body containing "no year detected" and the detail URL

#### Scenario: needs_review notification on mixed-type folder
- **WHEN** a Download has a mix of movie- and episode-typed files and transitions to `needs_review`
- **THEN** the ntfy push body lists "mixed file types — please confirm movie vs TV"

#### Scenario: Notification failure does not block status transition
- **WHEN** ntfy is unreachable
- **THEN** the Download still transitions to `needs_review` in the database and the error is logged

### Requirement: Notifications may include a custom icon
When `MEGAQUEUE_NTFY_ICON_URL` is configured, the system SHALL include an `Icon` header with that URL on every outbound ntfy.sh push notification (completion, failure, and needs_review). When `MEGAQUEUE_NTFY_ICON_URL` is not configured, notifications SHALL be sent without an `Icon` header, matching current behavior.

#### Scenario: Icon header sent when configured
- **WHEN** `MEGAQUEUE_NTFY_ICON_URL` is set to a public image URL and any notification (completion, failure, or needs_review) is sent
- **THEN** the outbound ntfy request includes an `Icon` header set to that URL

#### Scenario: No icon header when unconfigured
- **WHEN** `MEGAQUEUE_NTFY_ICON_URL` is not set and any notification is sent
- **THEN** the outbound ntfy request has no `Icon` header
