## Why

MegaQueue's ntfy.sh push notifications currently show ntfy's generic icon on iPhone. The user wants their "moviedog" branding to show instead. ntfy's iOS app (already free on the App Store) supports a per-notification `Icon` header pointing at a public HTTPS image, so this is achievable without publishing a custom app.

## What Changes

- Add an optional `MEGAQUEUE_NTFY_ICON_URL` config var (unset by default, not required at startup).
- When set, `notifications.py`'s `_send()` includes an `Icon` header with that URL on all outbound ntfy requests (completion, failure, needs_review).
- When unset, notifications behave exactly as today (no `Icon` header) — fully backward compatible.
- The icon image itself is hosted externally, on the user's separate public root-domain website (not under megaqueue's own `/static/`), because the megaqueue subdomain is protected by Cloudflare Access (GitHub IdP) and ntfy's servers/app cannot authenticate to fetch an asset from behind that gate. Hosting the PNG is an out-of-repo, manual step for the user — no new route or static asset is added to megaqueue itself.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `notifications`: notifications MAY now include a custom `Icon` header when a hosted icon URL is configured.
- `configuration`: adds the new optional `MEGAQUEUE_NTFY_ICON_URL` environment variable.

## Impact

- `megaqueue/megaqueue/config.py` — new optional config var.
- `megaqueue/megaqueue/notifications.py` — conditionally add `Icon` header in `_send()`.
- `megaqueue/tests/test_notifications.py` — new test coverage for the header being present/absent.
- No database, API, or dependency changes. No changes to `megaqueue/megaqueue/static/`.
