## ADDED Requirements

### Requirement: No app-level authentication
The application SHALL NOT perform any authentication checks. All routes SHALL be accessible without login. The application trusts that Cloudflare Access has authenticated the request before it reaches the tunnel.

#### Scenario: All routes accessible without credentials
- **WHEN** a request arrives at any application route
- **THEN** the application SHALL process it without checking for authentication headers, sessions, or passwords

### Requirement: Remove password authentication artifacts
The application SHALL NOT contain any password-based authentication code. The `auth.py` module, `hashpw.py` utility, `login.html` template, and `/login` and `/logout` routes SHALL be removed.

#### Scenario: No login page exists
- **WHEN** a user navigates to `/login`
- **THEN** the application SHALL return HTTP 404

#### Scenario: No auth module exists
- **WHEN** the application starts
- **THEN** it SHALL NOT import or reference `auth.py` or `bcrypt`

### Requirement: Remove password-related configuration
The application SHALL NOT require `MEGAQUEUE_PASSWORD_HASH`. The `MEGAQUEUE_SECRET_KEY` SHALL be retained only if needed for CSRF token signing.

#### Scenario: App starts without password hash
- **WHEN** the application starts without `MEGAQUEUE_PASSWORD_HASH` set
- **THEN** it SHALL start normally without error
