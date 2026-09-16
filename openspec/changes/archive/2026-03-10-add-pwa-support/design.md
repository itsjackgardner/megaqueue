## Context

MegaQueue is a Flask web app served via Waitress, primarily accessed from a phone browser over LAN or Cloudflare Tunnel. The UI uses Jinja2 templates with Tailwind CSS (CDN). Flask-Talisman manages security headers including Content Security Policy. There is no build step — all static assets are served directly.

## Goals / Non-Goals

**Goals:**
- Enable "Add to Home Screen" / "Install App" on mobile browsers (iOS Safari, Android Chrome)
- App opens in standalone mode (no browser address bar or navigation chrome)
- Themed status bar and splash screen matching the app's dark UI

**Non-Goals:**
- Offline support — MegaQueue requires a live connection to the server, caching pages offline adds complexity for no benefit
- Push notifications via service worker — ntfy.sh already handles push notifications
- App store distribution

## Decisions

**Minimal service worker:** The service worker will be a no-op stub that just listens for fetch events. Browsers require a service worker for the PWA install prompt, but we don't need caching or offline support. A minimal SW avoids cache invalidation bugs and keeps things simple.

*Alternative considered:* Cache-first strategy for static assets — rejected because Tailwind is loaded from CDN, the app is always online, and stale cache would cause more issues than it solves.

**Generated icons from a single SVG:** Ship a simple SVG icon and reference it at multiple sizes in the manifest. Modern browsers handle SVG icons well, avoiding the need to generate and maintain multiple PNG sizes.

*Alternative considered:* Multiple PNG icon files at 192x192 and 512x512 — still needed as fallback for older browsers/platforms, so we'll include both SVG and two PNG sizes.

**Inline service worker registration:** Add the SW registration script directly in `base.html` rather than a separate JS file. It's only 3-4 lines and doesn't warrant its own file.

## Risks / Trade-offs

**[iOS limitations]** → iOS Safari has limited PWA support (no install banner, must use "Add to Home Screen" manually). This is acceptable — the app still works, it's just a manual step.

**[CSP changes]** → The service worker needs `'self'` in `worker-src` CSP directive. This is a minimal, safe change since the SW is served from the same origin.
