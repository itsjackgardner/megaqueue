## 1. Megabasterd Fork

- [x] 1.1 Fork tonikelope/megabasterd, cherry-pick PR #704 commits (308f8e6, 05e9c63, f18e97a) onto current master
- [x] 1.2 Fix 404 bug — ensure API settings are initialized with defaults (enable_remote_api=yes, port=8127) so the API works out of the box
- [x] 1.3 Add CORS headers to all API responses for local development
- [ ] 1.4 Test all API endpoints: GET /status, POST /start, POST /stop, POST /pause, POST /resume, POST /clear509, POST /rename
- [ ] 1.5 Build fork JAR and verify it runs on Windows NUC with smart proxy + API enabled

## 2. Project Setup

- [x] 2.1 Create `megaqueue/` project directory structure with all folders (templates/, static/)
- [x] 2.2 Create `requirements.txt` with flask, sqlalchemy, requests, patool, flask-wtf, flask-talisman, waitress
- [x] 2.3 Create `config.py` with all configuration constants (MEGABASTERD_API_URL, MEGABASTERD_POLL_INTERVAL, MEGABASTERD_GRACE_PERIOD, PLEX_MOVIES_DIR, PLEX_TV_DIR, NTFY_TOPIC, NTFY_SERVER, SECRET_KEY, HOST, PORT) with environment variable override support and startup validation

## 3. Data Model

- [x] 3.1 Create `models.py` with SQLAlchemy Download model (fields: id, title, year, media_type, status, downloading_since, error_message, created_at, updated_at)
- [x] 3.2 Create DownloadFile model (fields: id, download_id FK, url, name, status, progress_bytes, total_bytes, speed, error_message, file_path) with cascade delete
- [x] 3.3 Add Download → DownloadFile relationship with eager loading, computed properties for aggregate progress_bytes, total_bytes, speed, file_paths, links
- [x] 3.4 Configure SQLite database with WAL mode and scoped_session for thread safety
- [x] 3.5 Add database initialization logic (create tables on first run)

## 4. Authentication & Security

- [x] 4.1 Configure Cloudflare Zero Trust + WARP for authentication (no app-level password)
- [x] 4.2 Configure Flask-WTF CSRF protection on all forms
- [x] 4.3 Configure Flask-Talisman security headers (X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy) with `force_https=False` (Cloudflare handles TLS)

## 5. Download Engine (Megabasterd REST API)

- [x] 5.1 Create `megabasterd_client.py` — HTTP client wrapper for megabasterd API (start, status, stop, clear509, pause, resume)
- [x] 5.2 Create `worker.py` polling worker — single `_poll_once` function called on interval that fetches megabasterd `/status`, syncs per-file progress to DB, derives download status from file statuses, triggers post-processing on all-finished
- [x] 5.3 Add URL normalization — handle old (`/#!id!key`) and new (`/file/id#key`) mega.nz URL formats for matching
- [x] 5.4 Add integrity sweep — detect files that disappear from megabasterd after grace period and mark them failed
- [x] 5.5 Move submission to Flask routes — `add_download` and `retry_download` call `mb_client.start()` directly
- [x] 5.6 Move cancellation to Flask routes — `cancel_download` calls `mb_client.stop()` for each file directly
- [x] 5.7 Add clear509 support — POST /clear509 when user triggers bandwidth error recovery
- [x] 5.8 Add startup validation — GET /status to verify megabasterd API is reachable, log clear error if not
- [x] 5.9 Worker clears finished downloads from megabasterd after post-processing via `POST /stop`

## 6. File Organizer

- [x] 6.1 Create `organizer.py` with movie organization logic: move files to `<PLEX_MOVIES_DIR>/<Title> (<Year>)/<filename>`
- [x] 6.2 Add TV organization logic: detect season from filename (S01E02 pattern), move to `<PLEX_TV_DIR>/<Title>/Season XX/<filename>`
- [x] 6.3 Add archive detection and extraction (`.rar`, `.001`, `.zip`, `.7z`) via patool, then organize extracted files
- [x] 6.4 Add temp directory cleanup after successful organization
- [x] 6.5 Update download status to "complete" or "failed" after organization, update individual DownloadFile file_path fields

## 7. Notifications

- [x] 7.1 Create `notifications.py` with ntfy.sh integration — POST on completion ("ready in Plex") and failure (include error reason)
- [x] 7.2 Add error handling so notification failures are logged but don't block the worker

## 8. Web UI — Flask Routes

- [x] 8.1 Create `app.py` with Flask app setup, database initialization, CSRF config, Talisman config, and worker thread startup
- [x] 8.2 Implement GET `/` dashboard route — query downloads sorted by status (downloading → queued → complete)
- [x] 8.3 Implement POST `/download` route — validate form, create Download + DownloadFile records, submit to megabasterd, redirect to dashboard
- [x] 8.4 Implement GET `/download/<id>` detail route — show full download info with per-file breakdown
- [x] 8.5 Implement POST `/download/<id>/retry` route — re-submit to megabasterd, reset all file statuses to queued
- [x] 8.6 Implement POST `/download/<id>/cancel` route — cancel via megabasterd API directly, update status
- [x] 8.7 Implement POST `/download/<id>/delete` route — remove download and cascade-delete files from database
- [x] 8.8 Implement POST `/download/<id>/clear509` route — trigger clear509 on megabasterd for stuck downloads
- [x] 8.9 Implement GET `/api/status` JSON endpoint — return all downloads with nested files as JSON for auto-refresh

## 9. Web UI — Templates & Frontend

- [x] 9.1 Create `templates/base.html` layout with Tailwind CDN, mobile-first viewport meta, nav
- [x] 9.2 Create `templates/index.html` dashboard — download cards with title, status badge, aggregate progress bar, speed, file count (e.g., "2/3 files"), cancel/retry/delete/clear509 buttons
- [x] 9.3 Create `templates/add.html` form — title input, year input, movie/tv toggle, links textarea, CSRF token, submit button
- [x] 9.4 Create `templates/detail.html` — overall progress, per-file breakdown (name/URL, status badge, progress bar, bytes, speed, error, file path)
- [x] 9.5 Create `static/refresh.js` — fetch `/api/status` every 5 seconds and update dashboard DOM (progress bars, speed, status badges) for both queued and downloading states

## 10. Integration & Polish

- [x] 10.1 Wire up worker → organizer → notifications pipeline (all files complete triggers organize, organize complete triggers notify)
- [x] 10.2 Add app entry point (`if __name__ == '__main__'`) that starts Waitress on HOST:PORT with worker thread
- [x] 10.3 Create README with setup instructions
- [ ] 10.4 Test end-to-end: add download via UI → verify megabasterd receives it → confirm per-file progress updates → confirm files appear in Plex folder → confirm notification sent
- [ ] 10.5 Test remote access: access via Cloudflare Tunnel domain from phone → add download → verify notification
