## ADDED Requirements

### Requirement: NTFY icon URL is configurable
The system SHALL support an optional `MEGAQUEUE_NTFY_ICON_URL` environment variable specifying a public HTTPS URL to an image used as the icon for ntfy.sh push notifications. This variable is optional and SHALL NOT be required at startup; when unset, notifications are sent without a custom icon.

#### Scenario: Icon URL configured
- **WHEN** `MEGAQUEUE_NTFY_ICON_URL` is set in the environment
- **THEN** the application starts normally and uses that URL when sending notifications

#### Scenario: Icon URL not configured
- **WHEN** `MEGAQUEUE_NTFY_ICON_URL` is not set
- **THEN** startup validation does not fail because of it, and notifications are sent without an icon
