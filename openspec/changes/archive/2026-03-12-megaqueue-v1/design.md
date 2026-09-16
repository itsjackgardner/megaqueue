## Context

Currently, downloading mega.nz content and getting it into Plex is a fully manual workflow: browse a forum, copy links, paste into megabasterd's Java GUI, wait for completion, then manually move files into the correct Plex library folder structure. This runs on a Windows 10 NUC that also hosts Plex. The goal is a single-user self-hosted web app accessible from a phone — both on the LAN and remotely when away from home. The user relies on megabasterd's smart proxy feature for bypassing MEGA's download speed limits, so megabasterd must be the download backend.

## Goals / Non-Goals

**Goals:**
- Single-command startup on the Windows NUC — no Docker, no external databases
- Mobile-first web UI that feels like a simplified Overseerr
- Per-file progress tracking with aggregate rollup on dashboard
- Reliable download processing with progress visibility
- Megabasterd as the download engine, preserving smart proxy functionality
- Automatic file organization into Plex-compatible folder structures
- Push notifications to phone on completion/failure
- Secure remote access from outside the local network via Cloudflare Tunnel
- Simple password authentication to protect the web UI
- Production-grade serving via Waitress with Flask-Talisman security headers

**Non-Goals:**
- Plex API integration or automatic library scanning
- Streaming or preview of downloaded content
- Bandwidth scheduling or download throttling
- Support for non-mega.nz download sources
- Direct public internet exposure (no port forwarding, no open firewall ports — Cloudflare Tunnel is outbound-only)
- Multi-user support or role-based access

## Decisions

### 1. Megabasterd fork with REST API as the download backend

**Choice:** Maintain a personal fork of megabasterd that re-adds the REST API from PR #704 (by EvanTrow). MegaQueue communicates with megabasterd entirely via this HTTP API — queuing downloads, polling progress, and cancelling jobs.

**Background on PR #704:** EvanTrow's PR added a REST API to megabasterd using Spark Framework (Java HTTP server). It was merged on March 20, 2025 and reverted the same day after the maintainer reported 404 errors on `http://localhost:8217`. The 404 was likely a configuration issue — the API requires `enable_remote_api=yes` and a port number in megabasterd's settings DB, and the constructor returns early if these aren't set. The code itself (RemoteAPI.java) is clean and functional.

**API endpoints provided by the fork:**
- `GET /status` — returns all downloads with progress (bytes loaded/total), speed, status, error info, 509 bandwidth error counts
- `POST /start` — queue new downloads (`{"urls": "mega.nz/...", "dest": "optional/subfolder"}`)
- `POST /stop` — stop a download and optionally delete files (`{"url": "...", "delete": true}`)
- `POST /pause` — pause all downloads
- `POST /resume` — resume all downloads
- `POST /clear509` — clear 509 bandwidth limit errors and restart affected chunk workers
- `POST /rename` — rename a completed download's file

**Alternatives considered:**
- **Filesystem bridge (write .mega files, poll output dir):** Loosely coupled but can't queue downloads programmatically, no progress tracking, no cancel support. Hand-wavy "bridge" component needed.
- **Direct megabasterd DB manipulation:** Undocumented schema, risk of corruption (Issue #288), megabasterd may not pick up externally-inserted rows.
- **GUI automation (pyautogui):** Extremely fragile, requires visible window, breaks on UI changes.
- **MEGAcmd (`mega-get`):** Official CLI, easy to script, but does not support smart proxy. Speed limits would be a blocker.
- **Reimplement smart proxy in Python:** Would need to implement MEGA's download protocol + proxy rotation from scratch. Massive effort for unclear benefit.

**Rationale:** The fork approach gives us a proper HTTP API with full control: queue, progress, cancel, pause/resume. The PR code is ~400 lines of straightforward Java. The maintenance burden is low — we cherry-pick the API commits onto new megabasterd releases. Smart proxy, multi-slot downloads, and all megabasterd features work unchanged. The fork needs three fixes:
1. Ensure API settings are initialized with sensible defaults (fix the 404)
2. Add CORS headers for local development
3. Test with current megabasterd master

### 2. SQLite via SQLAlchemy

**Choice:** SQLite database with SQLAlchemy ORM.

**Alternatives considered:**
- **PostgreSQL/MySQL:** Overkill for single-user app, adds installation complexity on Windows.
- **JSON file:** Too fragile for concurrent read/write from web thread + worker thread.

**Rationale:** Zero-config, file-based, sufficient for single-user workload. SQLAlchemy provides a clean data layer and handles thread safety with `scoped_session`.

### 3. Polling worker architecture with Flask-side submission

**Choice:** Flask routes submit downloads to megabasterd directly. A background worker thread polls megabasterd's `/status` endpoint on an interval and syncs state back to the database. The worker does not submit downloads — it only observes and reacts to megabasterd's state.

**Alternatives considered:**
- **Worker-side submission with sequential processing:** Original approach. Worker picked one queued download at a time, submitted it, and polled in a blocking loop. Problems: no parallelism, no crash recovery for "downloading" records, single point of failure.
- **Celery + Redis:** Massive overhead for a single-user queue.
- **asyncio:** Would complicate subprocess management and Flask integration for no real benefit.

**Rationale:** Separating submission (Flask) from monitoring (worker) gives cleaner responsibilities. The worker polls once per tick and updates all active downloads simultaneously. An integrity sweep catches downloads that disappear from megabasterd after a configurable grace period (default 30s), providing crash recovery. The grace period prevents race conditions between Flask submission and the worker's next poll.

### 4. Jinja2 + Tailwind CDN for UI

**Choice:** Server-rendered templates with Tailwind CSS via CDN and minimal vanilla JS for auto-refresh.

**Alternatives considered:**
- **React/Vue SPA:** Adds build tooling, separate dev server, and complexity for a simple CRUD UI.
- **HTMX:** Good fit but adds a dependency for something achievable with 20 lines of fetch().

**Rationale:** No build step, no JS framework, no node_modules. Tailwind CDN keeps styling clean. A small `refresh.js` script polls `/api/status` every 5 seconds to update the dashboard.

### 5. ntfy.sh for push notifications

**Choice:** HTTP POST to ntfy.sh public server (or self-hosted).

**Alternatives considered:**
- **Telegram bot:** Requires bot registration and API tokens.
- **Email:** Slow, not push, requires SMTP config.
- **Pushover:** Paid service.

**Rationale:** ntfy.sh is free, requires no signup, and works with a simple HTTP POST. The phone app subscribes to a topic (a long random string acts as a private channel). Trivial to integrate.

### 6. Archive extraction via patool/7z

**Choice:** Use `patool` (Python library wrapping 7z/unrar) for multi-part archive extraction.

**Alternatives considered:**
- **Direct 7z subprocess:** Works but patool provides a unified interface across archive types.
- **Skip extraction:** Would require manual intervention, defeating the purpose.

**Rationale:** Forum downloads frequently come as split RAR archives. patool auto-detects format and delegates to installed extractors. Falls back to 7z subprocess if patool isn't available.

### 7. Cloudflare Tunnel for remote access

**Choice:** Use Cloudflare Tunnel (cloudflared) to make the app accessible from outside the local network at a custom HTTPS domain.

**Alternatives considered:**
- **Tailscale:** Simpler setup, most secure (app invisible to public internet). But requires installing the Tailscale app on the phone and keeping VPN active. No browser-only access.
- **Reverse proxy + DDNS + port forwarding:** Traditional approach. Requires opening ports on the router, dynamic DNS, Let's Encrypt cert management. Larger attack surface. Some ISPs block ports or use CGNAT.
- **ngrok:** Free tier has 1,000 requests/day limit and 1 GB/month bandwidth cap. Interstitial warning page on all browser traffic. Not suitable for always-on use.
- **No remote access:** User specifically wants phone access away from home.

**Rationale:** Cloudflare Tunnel is the best fit for browser-based remote access:
- **Zero port forwarding** — cloudflared makes outbound-only connections to Cloudflare's edge. No ports opened on router.
- **HTTPS automatic** — Cloudflare handles TLS termination. The phone accesses MegaQueue at `https://megaqueue.yourdomain.com`.
- **No phone app needed** — just a browser. No VPN client to install or keep running.
- **Cloudflare Access (free)** — optional zero-trust authentication layer (email OTP) in front of the app. Up to 50 users on free tier.
- **DDoS protection and WAF** — included on Cloudflare's free tier.
- **Runs as a Windows service** — cloudflared installs as a service, survives reboots, auto-reconnects.
- **No bandwidth caps** — tunnels are completely free with no limits.
- **Cost:** Requires a domain name (~$10/year). Cloudflare DNS and tunnels are free.

### 8. Waitress as production WSGI server

**Choice:** Use Waitress to serve the Flask app instead of Flask's built-in development server.

**Alternatives considered:**
- **Flask dev server (`app.run()`):** Not designed for production. Single-threaded, no connection handling, verbose debug output.
- **Gunicorn:** Industry standard but Linux-only. Does not run on Windows.
- **Hypercorn/Uvicorn:** ASGI servers, overkill for a sync Flask app.

**Rationale:** Waitress is a pure-Python production WSGI server that runs natively on Windows. No compilation, no C dependencies. Handles concurrent connections properly, has configurable thread pool, and is the standard recommendation for Flask on Windows.

### 9. Flask-Talisman for security headers

**Choice:** Use Flask-Talisman to add security headers to all responses.

**Alternatives considered:**
- **Manual header setting:** Error-prone, easy to forget on new routes.
- **No security headers:** Leaves the app vulnerable to clickjacking, MIME sniffing, and other browser-based attacks.

**Rationale:** Flask-Talisman adds HSTS, Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, and Referrer-Policy headers with a single line of configuration. Important since the app is exposed to the internet via Cloudflare Tunnel. Note: HTTPS enforcement is handled by Cloudflare, so Talisman's `force_https` should be disabled (local traffic between cloudflared and Flask is HTTP on localhost).

### 10. Cloudflare Zero Trust + WARP for authentication

**Choice:** Rely on Cloudflare Zero Trust (Access) with WARP client for authentication. No app-level password.

**Alternatives considered:**
- **App-level password auth (bcrypt + Flask sessions):** Previously used. Removed in favor of Cloudflare Access which provides stronger security (email OTP, device posture) without managing passwords.
- **Flask-Login with user model:** Overengineered for a single user.
- **HTTP Basic Auth:** No logout, credentials sent on every request, ugly browser prompt.

**Rationale:** Cloudflare Access provides zero-trust authentication at the network edge. The app trusts that any request reaching it has been authenticated by Cloudflare. This eliminates password management, session handling, and login UI from the app. WARP client on the phone ensures all traffic goes through Cloudflare's network.

## Risks / Trade-offs

- **Maintaining a megabasterd fork** → The fork must be kept in sync with upstream megabasterd releases. Mitigation: The API is a single file (RemoteAPI.java) + minor changes to MainPanel, DBTools, and pom.xml. Cherry-picking onto new releases should be low-friction. If upstream ever adds an official API, we can drop the fork.
- **Megabasterd API stability** → The API reads download state from Swing UI components (e.g., `getStatus_label().getText()`), which is fragile if the UI text changes. Mitigation: For our fork, we can refactor status checks to use internal state rather than UI labels.
- **Megabasterd must be running with API enabled** → MegaQueue depends on megabasterd running with the REST API configured. Mitigation: Startup validation pings `GET /status` and logs a clear error if megabasterd is unreachable.
- **Smart proxy config is GUI-only** → User must configure smart proxy settings in megabasterd's GUI once. MegaQueue cannot modify these settings. Mitigation: Document the one-time setup in a README.
- **Domain name required** → Cloudflare Tunnel requires a domain pointed at Cloudflare DNS (~$10/year). Mitigation: Cheap, one-time setup, and unlocks Cloudflare's free security features (DDoS, WAF, Access).
- **Cloudflare as a dependency** → Remote access depends on Cloudflare's infrastructure. Mitigation: LAN access still works if Cloudflare is down. Cloudflare has near-100% uptime.
- **cloudflared Windows service setup** → Requires copying credential files and editing registry for service install. Mitigation: One-time setup, documented in README.
- **SQLite concurrent access from web + worker threads** → Mitigation: Use SQLAlchemy scoped sessions with WAL mode. Single-user app means low contention.
- **Windows path handling** → Mitigation: Use `pathlib.Path` throughout for cross-platform path operations.
- **Large file downloads may fail mid-way** → Mitigation: Megabasterd handles resume internally. Worker detects failure via API status and can resubmit.
