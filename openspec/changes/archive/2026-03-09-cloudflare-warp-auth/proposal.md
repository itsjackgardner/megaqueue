## Why

The web app currently uses a single bcrypt password for authentication. This means typing a password on every new session (especially annoying on iPhone), no per-user access control, and no protection against brute-force attacks. Cloudflare WARP + Zero Trust Access can authenticate devices transparently — no login page, no passwords — while making it trivial to grant or revoke access for friends.

## What Changes

- **Remove** password-based authentication entirely (bcrypt hash, login form, `@login_required` decorator, Flask sessions, auth module)
- **Remove** `MEGAQUEUE_PASSWORD_HASH` and `MEGAQUEUE_SECRET_KEY` environment variables
- **Remove** `hashpw.py` utility, `auth.py` module, `login.html` template
- **Remove** `bcrypt` dependency
- **Trust Cloudflare Access** at the network layer — no app-level JWT validation needed since the tunnel is the only ingress path
- **Update** Cloudflare tunnel setup docs to include Zero Trust Access policy and WARP enrollment steps

## Capabilities

### New Capabilities
- `cloudflare-warp-setup`: Documentation and configuration for Cloudflare Zero Trust Access + WARP device enrollment, replacing password-based login

### Modified Capabilities

## Impact

- **Code**: `auth.py` deleted, `login.html` deleted, `hashpw.py` deleted, `app.py` routes simplified (no login/logout, no `@login_required`)
- **Dependencies**: Remove `bcrypt`. Remove `flask-wtf` if CSRF is no longer needed (check if any POST forms remain that need it).
- **Config**: Remove `MEGAQUEUE_PASSWORD_HASH` and `MEGAQUEUE_SECRET_KEY`
- **Infrastructure**: Requires Cloudflare Zero Trust (free tier), WARP app on authorized devices, and an Access Application policy on the tunnel subdomain
- **Docs**: README Cloudflare section needs rewrite for Zero Trust + WARP setup
