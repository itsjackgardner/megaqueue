## MODIFIED Requirements

### Requirement: Web app manifest
The application SHALL serve a web app manifest at `/static/manifest.json` that declares the app name as "movie dog", short_name as "movie dog", display mode as "standalone", theme color as "#3B4CF6", background color as "#111827", start URL as "/", and icon references at 192x192 and 512x512 sizes in PNG format plus an SVG icon.

#### Scenario: Browser reads manifest
- **WHEN** a browser loads any page of the application
- **THEN** the HTML contains a `<link rel="manifest">` tag pointing to the manifest file

#### Scenario: Manifest contains required fields
- **WHEN** the manifest file is fetched
- **THEN** it contains `name` set to "movie dog", `short_name` set to "movie dog", `start_url`, `display`, `theme_color` set to "#3B4CF6", `background_color` set to "#111827", and `icons` fields

### Requirement: App icons
The application SHALL include app icons at `/static/icons/` in the following formats: `icon-192.png` (192x192), `icon-512.png` (512x512), and `icon.svg` (scalable). All icons SHALL depict the movie dog mascot (white dog with party hat on vibrant blue background).

#### Scenario: Icons are accessible
- **WHEN** a browser requests any icon referenced in the manifest
- **THEN** the server returns the icon file with the correct content type

#### Scenario: Icons reflect movie dog brand
- **WHEN** the icons are displayed (e.g., on home screen, app switcher)
- **THEN** they show the movie dog mascot on a vibrant blue background
