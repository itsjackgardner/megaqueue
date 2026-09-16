## Why

Downloading files from mega.nz links found on a forum, organizing them into Plex library folders, and getting notified on completion is currently a tedious manual process involving megabasterd's GUI, manual file moves, and no mobile access. A lightweight self-hosted web app would turn this into an Overseerr-like experience — queue downloads from your phone (even away from home) and forget about them until a push notification says they're ready.

## What Changes

- New Python/Flask web application ("MegaQueue") running on the Windows NUC alongside Plex
- Mobile-first web UI for pasting mega.nz links, naming downloads, and monitoring queue status
- Background download worker using megabasterd as the download engine (leveraging its smart proxy feature for bypassing MEGA speed limits)
- Automatic file organization into Plex-compatible folder structures (`Movies/Title (Year)/`, `TV/Title/Season XX/`)
- Multi-part archive extraction (`.rar`, `.001` files) before organizing
- Push notifications via ntfy.sh on download completion or failure
- SQLite database for persistent download queue and history
- Secure remote access via Cloudflare Tunnel so the app is reachable from outside the local network without opening ports
- Production WSGI server (Waitress) and security headers (Flask-Talisman) for safe internet exposure

## Capabilities

### New Capabilities

- `web-ui`: Mobile-first Flask/Jinja2/Tailwind interface with password authentication — add downloads, view dashboard with status/progress, retry/delete items, auto-refresh polling. Served via Waitress (production WSGI) with Flask-Talisman security headers. Accessible remotely via Cloudflare Tunnel.
- `download-engine`: Flask routes submit downloads to megabasterd via REST API. Background polling worker monitors megabasterd's `/status` endpoint, syncs per-file progress to the database, detects completion/errors, and triggers post-processing. Integrity sweep catches downloads that disappear from megabasterd after a grace period.
- `file-organizer`: Post-download file mover that structures files into Plex library folders by media type, extracts multi-part archives, and cleans up temp directories
- `notifications`: ntfy.sh integration for push notifications on download completion and failure events
- `data-model`: SQLAlchemy/SQLite data layer — Download model with DownloadFile children for per-file tracking. Status lifecycle: queued → downloading → processing → complete → failed. Download status derived from individual file statuses.
- `configuration`: Centralized config for Plex library paths, megabasterd paths, temp download directory, ntfy topic, authentication secret, and Cloudflare Tunnel settings
- `remote-access`: Cloudflare Tunnel-based secure remote access — cloudflared daemon proxies traffic from a custom domain (HTTPS) to the local Flask app. No port forwarding needed. Cloudflare Access provides an additional zero-trust authentication layer.

### Modified Capabilities

_(none — greenfield project)_

## Impact

- **New dependencies:** Flask, SQLAlchemy, requests, patool (or 7z subprocess for archive extraction), bcrypt, flask-wtf, flask-talisman, waitress
- **External services:** megabasterd fork (with REST API) must be installed and running on the NUC with smart proxy configured and API enabled; ntfy.sh for push notifications; cloudflared daemon for remote access; domain name pointed at Cloudflare DNS
- **Network:** App listens on localhost:5000 (Waitress). Locally accessible via LAN IP. Remotely accessible via Cloudflare Tunnel at a custom HTTPS domain. No ports opened on router.
- **Security:** Password-protected login (single-user). Cloudflare Tunnel provides encrypted transport + optional Cloudflare Access zero-trust layer. Flask-Talisman adds security headers (HSTS, CSP, X-Content-Type-Options). CSRF protection on all forms.
- **Filesystem:** Writes to a temp download directory and Plex library folders on the NUC's drives
