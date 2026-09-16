## Why

MegaQueue is designed to be used from a phone browser. Adding PWA support lets users install it to their home screen so it opens like a native app — no browser chrome, faster access, and a more polished experience. This is a small addition with high usability impact.

## What Changes

- Add a web app manifest (`manifest.json`) with app name, icons, theme color, and standalone display mode
- Add a minimal service worker to satisfy browser PWA install criteria
- Update `base.html` to reference the manifest and register the service worker
- Add a set of app icons at standard PWA sizes
- Update Content Security Policy to allow the service worker and manifest

## Capabilities

### New Capabilities
- `pwa`: Web app manifest, service worker registration, and app icons enabling "Add to Home Screen" installation on mobile devices

### Modified Capabilities
- `web-ui`: CSP headers need updating to allow manifest and service worker resources

## Impact

- **Files added**: `static/manifest.json`, `static/sw.js`, `static/icons/` (icon files)
- **Files modified**: `templates/base.html` (manifest link, SW registration script), `app.py` (CSP update)
- **Dependencies**: None — pure frontend addition
- **Breaking changes**: None
