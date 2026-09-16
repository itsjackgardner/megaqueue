## Context

MegaQueue's `notifications.py` sends push notifications via ntfy.sh using plain HTTP POSTs with `Title` and `Priority` headers. ntfy's iOS client supports an additional `Icon` header: a public HTTPS URL to a PNG/JPEG that renders as the notification's icon. The megaqueue subdomain is exposed via Cloudflare Tunnel and gated by Cloudflare Access (GitHub IdP) — see `openspec/specs/cloudflare-access-auth/spec.md` — so any asset served from megaqueue's own `/static/` path would require an authenticated fetch, which ntfy's servers/app cannot perform.

## Goals / Non-Goals

**Goals:**
- Let notifications carry a custom icon on devices that support it (ntfy iOS app), with zero impact when not configured.
- Keep the icon hosting outside megaqueue's auth boundary so ntfy can fetch it unauthenticated.

**Non-Goals:**
- Serving or storing the icon image within megaqueue itself (no new route or static asset).
- Validating that the configured URL is reachable or a valid image at startup — that's on the user, same as any other externally-hosted resource.
- Per-notification-type icons (completion vs. failure vs. needs_review) — one icon URL for all.

## Decisions

- **Config**: add `NTFY_ICON_URL = _env("NTFY_ICON_URL")` in `config.py`, optional, not added to `_REQUIRED`, defaults to `None`.
- **Header wiring**: in `notifications.py`'s `_send()`, build the headers dict as today, then conditionally add `headers["Icon"] = config.NTFY_ICON_URL` only if the value is truthy. This keeps existing tests (which don't set the var) passing unchanged.
- **Icon hosting**: out of scope for this repo. The user hosts the PNG on their separate public root-domain website (no Cloudflare Access) and points `MEGAQUEUE_NTFY_ICON_URL` at it. Considered hosting under megaqueue's `/static/` with a Cloudflare Access bypass policy for that one path — rejected as it requires an out-of-band Cloudflare dashboard change and couples the notification feature to Access configuration, whereas using the existing public site needs no infra changes at all.
- **Image format**: rely on the user providing a PNG/JPEG (ntfy's Icon header does not reliably render SVG on iOS) — no in-app conversion or validation.

## Risks / Trade-offs

- [If the externally-hosted icon URL becomes unreachable or is removed] → ntfy simply fails to render the icon and falls back to its default; does not affect notification delivery or content, so no mitigation needed in code.
- [Icon URL is a plaintext HTTP header value] → no sensitive data involved (just a public image URL), no additional mitigation needed.
