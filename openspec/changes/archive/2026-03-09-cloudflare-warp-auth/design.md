## Context

MegaQueue is a Flask web app accessed over a Cloudflare Tunnel at `queue.<domain>`. It currently uses a single bcrypt password with Flask sessions. The app runs on a Windows NUC on the local network (port 5000) and is only exposed externally through the tunnel.

Cloudflare Zero Trust Access can sit in front of the tunnel and authenticate users via WARP device enrollment before requests ever reach the app. Since the tunnel is the only ingress path (no inbound ports are open), the app can trust that any request it receives has already been authenticated by Cloudflare.

## Goals / Non-Goals

**Goals:**
- Passwordless authentication — WARP-enrolled devices access the app with zero login friction
- Per-device access control — grant/revoke access to specific people via Cloudflare dashboard
- Simplify the app by removing all auth code

**Non-Goals:**
- App-level JWT validation — Cloudflare Access handles auth at the network layer; the tunnel is the only way in
- Multi-user features within the app (e.g., per-user download queues)
- Automated Cloudflare infrastructure provisioning — manual dashboard setup is fine
- Fallback to password auth

## Decisions

### 1. Trust Cloudflare Access entirely, no app-level JWT validation

**Choice**: Remove all authentication code from the Flask app. If a request reaches the app, it's authorized.

**Why**: The app is only reachable through the Cloudflare Tunnel (`cloudflared` makes an outbound connection — no inbound ports). Cloudflare Access blocks unauthenticated requests before they reach the tunnel. Adding JWT validation would be defense-in-depth for a threat that doesn't exist (direct LAN access is acceptable for the owner).

**Alternative considered**: Validate `Cf-Access-Jwt-Assertion` header in the app. Rejected — adds complexity (PyJWT, JWKS caching, new env vars) for no practical security benefit in this setup.

### 2. Remove all auth-related code and dependencies

**Choice**: Delete `auth.py`, `hashpw.py`, `login.html`, login/logout routes, `@login_required` decorator, and `bcrypt` dependency.

**Why**: With no app-level auth, this code is dead weight. Clean removal is better than leaving it dormant.

### 3. Evaluate whether flask-wtf / CSRF is still needed

**Choice**: Check if any POST forms remain after removing the login form. The add-download form uses POST, so flask-wtf and CSRF protection should likely stay.

**Why**: CSRF protection is a separate concern from authentication — it prevents cross-site request forgery even when auth is handled externally.

### 4. Remove SECRET_KEY if sessions are no longer used

**Choice**: If flask-wtf CSRF is kept, `SECRET_KEY` is still needed (CSRF tokens are signed with it). If flask-wtf is removed, `SECRET_KEY` can go too.

**Why**: Minimize config surface. Only keep what's actively used.

## Risks / Trade-offs

- **[LAN access is unauthenticated]** → Anyone on the local network can hit `localhost:5000`. Mitigation: acceptable for a personal NUC on a home network. The owner may actually prefer LAN access without needing WARP.
- **[Cloudflare dependency]** → Auth is entirely in Cloudflare's hands. If their Access policy misconfigures, the app is exposed. Mitigation: simple policy (WARP + email allow list), easy to verify in dashboard.
