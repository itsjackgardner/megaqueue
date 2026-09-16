## ADDED Requirements

### Requirement: App is served by Waitress production WSGI server
The system SHALL use Waitress as the WSGI server instead of Flask's built-in development server. Waitress binds to `0.0.0.0:5000` and handles concurrent connections with a thread pool.

#### Scenario: App starts via Waitress
- **WHEN** the application is launched
- **THEN** Waitress serves the Flask app on `0.0.0.0:5000` with production-appropriate settings (no debug mode, no reloader)

### Requirement: App is accessible remotely via Cloudflare Tunnel
The system SHALL be accessible from outside the local network via a Cloudflare Tunnel. The cloudflared daemon runs as a Windows service on the NUC and proxies HTTPS traffic from a custom domain to the local Flask app on localhost:5000.

#### Scenario: Remote access via custom domain
- **WHEN** the user opens `https://megaqueue.yourdomain.com` on their phone browser (away from home)
- **THEN** Cloudflare routes the request through the tunnel to the Flask app and the user sees the login page

#### Scenario: LAN access still works
- **WHEN** the user is on the same local network as the NUC
- **THEN** the user can access MegaQueue at `http://<lan-ip>:5000` directly without going through Cloudflare

### Requirement: Flask-Talisman adds security headers to all responses
The system SHALL use Flask-Talisman to add security headers including X-Content-Type-Options, X-Frame-Options, Referrer-Policy, and Content-Security-Policy. HTTPS enforcement (`force_https`) SHALL be disabled since TLS termination is handled by Cloudflare, not the Flask app.

#### Scenario: Security headers are present on responses
- **WHEN** a browser makes any request to the app
- **THEN** the response includes `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and a Content-Security-Policy header

#### Scenario: Talisman does not force HTTPS redirect
- **WHEN** a request arrives over HTTP (from cloudflared on localhost)
- **THEN** Talisman does not redirect to HTTPS (since Cloudflare handles TLS externally)

### Requirement: Authentication via Cloudflare Zero Trust
The system SHALL rely on Cloudflare Zero Trust (Access) with WARP client for authentication. No app-level password or login page is required — Cloudflare authenticates all requests at the network edge before they reach the app.

#### Scenario: Authenticated user accesses app
- **WHEN** a user with a valid Cloudflare WARP session visits the app
- **THEN** the request passes through Cloudflare Access and reaches the Flask app without any app-level login

#### Scenario: Unauthenticated user is blocked
- **WHEN** a user without a valid Cloudflare session tries to access the app remotely
- **THEN** Cloudflare Access blocks the request before it reaches the Flask app

### Requirement: CSRF protection on all forms
The system SHALL include CSRF tokens on all state-changing forms (add download, retry, delete, login) to prevent cross-site request forgery.

#### Scenario: Missing CSRF token is rejected
- **WHEN** a POST request arrives without a valid CSRF token
- **THEN** the server responds with 400 Bad Request

### Requirement: No open ports on router
The system SHALL NOT require any port forwarding on the router. Cloudflare Tunnel uses outbound-only connections from the cloudflared daemon to Cloudflare's edge network.

#### Scenario: Router has no port forwarding rules
- **WHEN** the NUC is behind a standard home router with no port forwarding configured
- **THEN** the app is still accessible remotely via the Cloudflare Tunnel domain
