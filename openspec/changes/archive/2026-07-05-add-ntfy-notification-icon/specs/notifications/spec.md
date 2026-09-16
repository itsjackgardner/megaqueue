## ADDED Requirements

### Requirement: Notifications may include a custom icon
When `MEGAQUEUE_NTFY_ICON_URL` is configured, the system SHALL include an `Icon` header with that URL on every outbound ntfy.sh push notification (completion, failure, and needs_review). When `MEGAQUEUE_NTFY_ICON_URL` is not configured, notifications SHALL be sent without an `Icon` header, matching current behavior.

#### Scenario: Icon header sent when configured
- **WHEN** `MEGAQUEUE_NTFY_ICON_URL` is set to a public image URL and any notification (completion, failure, or needs_review) is sent
- **THEN** the outbound ntfy request includes an `Icon` header set to that URL

#### Scenario: No icon header when unconfigured
- **WHEN** `MEGAQUEUE_NTFY_ICON_URL` is not set and any notification is sent
- **THEN** the outbound ntfy request has no `Icon` header
