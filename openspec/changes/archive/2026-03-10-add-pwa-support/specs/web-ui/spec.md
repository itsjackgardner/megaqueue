## MODIFIED Requirements

### Requirement: Security headers
The application SHALL configure Flask-Talisman with `force_https=False`, `session_cookie_secure=False`, and a Content Security Policy that includes `worker-src 'self'` to allow service worker registration, in addition to the existing `default-src`, `script-src`, and `style-src` directives.

#### Scenario: Service worker allowed by CSP
- **WHEN** the browser attempts to register a service worker from the same origin
- **THEN** the Content Security Policy permits the registration without errors

#### Scenario: Existing CSP rules preserved
- **WHEN** the browser loads a page with Tailwind CSS from CDN and inline styles
- **THEN** the existing `script-src` and `style-src` CSP rules continue to allow these resources
