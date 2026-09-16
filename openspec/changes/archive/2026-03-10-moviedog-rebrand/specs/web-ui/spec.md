## MODIFIED Requirements

### Requirement: Security headers
The application SHALL configure Flask-Talisman with `force_https=False`, `session_cookie_secure=False`, and a Content Security Policy that includes `worker-src 'self'` to allow service worker registration, in addition to the existing `default-src`, `script-src`, and `style-src` directives.

#### Scenario: Service worker allowed by CSP
- **WHEN** the browser attempts to register a service worker from the same origin
- **THEN** the Content Security Policy permits the registration without errors

#### Scenario: Existing CSP rules preserved
- **WHEN** the browser loads a page with Tailwind CSS from CDN and inline styles
- **THEN** the existing `script-src` and `style-src` CSP rules continue to allow these resources

## ADDED Requirements

### Requirement: movie dog theme meta tags
The base HTML template SHALL set the `<meta name="theme-color">` to "#3B4CF6", `<meta name="apple-mobile-web-app-title">` to "movie dog", and the `<title>` tag SHALL display "movie dog" as the app name prefix.

#### Scenario: Theme color meta tag updated
- **WHEN** a page is loaded
- **THEN** the `<meta name="theme-color">` content is "#3B4CF6"

#### Scenario: Apple web app title is movie dog
- **WHEN** a user adds the app to their iOS home screen
- **THEN** the default name shown is "movie dog"

### Requirement: movie dog accent colors
All primary action buttons and accent UI elements SHALL use Tailwind `indigo-600` (with `indigo-700` hover) instead of the previous `blue-600`/`blue-700`. Progress bars and status-specific colors (blue for downloading, green for complete, etc.) MAY remain unchanged.

#### Scenario: Primary buttons use indigo
- **WHEN** a primary button is rendered (e.g., "Add Download", "Retry")
- **THEN** it has `bg-indigo-600` and `hover:bg-indigo-700` classes

#### Scenario: Status colors unchanged
- **WHEN** a download item displays a status badge
- **THEN** status-specific colors (blue/yellow/purple/green/red/gray) remain as before
