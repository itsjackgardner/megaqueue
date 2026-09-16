## 1. Static Assets

- [x] 1.1 Create `static/manifest.json` with app name, short_name, start_url, display (standalone), theme_color, background_color, and icon references
- [x] 1.2 Create `static/icons/icon.svg` — simple MQ logo for the app icon
- [x] 1.3 Create `static/icons/icon-192.png` and `static/icons/icon-512.png` from the SVG
- [x] 1.4 Create `static/sw.js` — minimal service worker with a fetch listener that passes all requests through to the network

## 2. Template Changes

- [x] 2.1 Add `<link rel="manifest" href="/static/manifest.json">` to `templates/base.html` head
- [x] 2.2 Add `<meta name="theme-color">` tag matching the manifest theme_color
- [x] 2.3 Add `<meta name="apple-mobile-web-app-capable" content="yes">` and `<meta name="apple-mobile-web-app-status-bar-style">` for iOS support
- [x] 2.4 Add `<link rel="apple-touch-icon" href="/static/icons/icon-192.png">` for iOS home screen icon
- [x] 2.5 Add inline script to register the service worker via `navigator.serviceWorker.register('/static/sw.js')`

## 3. CSP Update

- [x] 3.1 Add `worker-src: 'self'` to the Content Security Policy in `app.py` Talisman config
