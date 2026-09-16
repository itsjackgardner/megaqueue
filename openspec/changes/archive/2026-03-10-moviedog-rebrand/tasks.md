## 1. Icon Assets

- [x] 1.1 Create new `icon.svg` with simplified movie dog mascot (white dog head + party hat on #3B4CF6 rounded-rect background) in `megaqueue/static/icons/`
- [x] 1.2 Generate `icon-192.png` (192x192) from the new icon/mascot source
- [x] 1.3 Generate `icon-512.png` (512x512) from the new icon/mascot source

## 2. PWA Manifest

- [x] 2.1 Update `megaqueue/static/manifest.json`: change `name` and `short_name` to "movie dog", `theme_color` to "#3B4CF6", keep `background_color` as "#111827"

## 3. HTML Base Template

- [x] 3.1 Update `<title>` in `megaqueue/templates/base.html` from "MegaQueue" to "movie dog"
- [x] 3.2 Update `<meta name="theme-color">` content to "#3B4CF6"
- [x] 3.3 Update `<meta name="apple-mobile-web-app-title">` content to "movie dog" (add if not present)
- [x] 3.4 Update nav bar app name text from "MegaQueue" to "movie dog"

## 4. Accent Color Update

- [x] 4.1 Replace `blue-600` with `indigo-600` and `blue-700` with `indigo-700` in primary button classes across all templates
- [x] 4.2 Replace `blue-500` with `indigo-500` for progress bar color (if used as accent, not status)
- [x] 4.3 Verify status-specific colors (downloading=blue, queued=yellow, etc.) are left unchanged

## 5. Verification

- [ ] 5.1 Load the app in browser and confirm "movie dog" appears in tab title and nav bar
- [ ] 5.2 Verify new icon appears in browser tab and manifest
- [ ] 5.3 Confirm accent buttons are indigo-toned and status badges retain original colors
