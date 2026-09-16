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
