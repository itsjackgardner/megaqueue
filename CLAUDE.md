# MegaQueue

Python Flask app that queues mega.nz downloads via a vendored megapull library, organizes files into Plex library folders, and sends push notifications. Runs in Docker on Linux.

## Project Structure

```
megaqueue/              # Package directory (all source code)
├── __init__.py
├── app.py              # Flask app, routes, startup validation
├── config.py           # All config via MEGAQUEUE_* env vars
├── enums.py            # StrEnum types (DownloadStatus, FileStatus, MediaType, …)
├── models.py           # SQLAlchemy models (Download, DownloadFile)
├── migrations.py       # Named, ordered schema migrations called from init_db()
├── worker.py           # Background thread — drives the poll loop
├── sync.py             # Download engine ↔ DB sync (matching, folder expansion, file updates)
├── lifecycle.py        # Status derivation, post-processing orchestration
├── mega_urls.py        # Pure URL helpers (normalise, extract_folder_id, is_folder_url)
├── metadata.py         # guessit-driven metadata aggregation (title/year/media_type)
├── mega_downloader.py  # In-process MEGA download manager (async bridge to megapull)
├── megapull/           # Vendored megapull library (async MEGA downloads via httpx)
├── organiser.py        # Hand-rolled organiser (movies + extras, TV episodes)
├── notifications.py    # ntfy.sh push notifications
├── static/             # JS, icons, PWA manifest
└── templates/          # Jinja2 HTML templates
run.py                  # Entrypoint: python run.py
tests/                  # pytest test suite
requirements.txt
requirements-dev.txt
```

## Architecture

```
User (phone browser) → Flask Web UI → Database (SQLite)
                                    ↕ (background worker polls every 5s)
                              MegaDownloadManager (in-process, async)
                                    ↓ (on completion)
                              File Organizer → Plex library folders
                                    ↓
                              ntfy.sh push notification
```

### Data Model

Two SQLAlchemy models:
- **`Download`** — One per user-submitted queue entry. Fields: `title`, `year`, `media_type` (movie|tv), `status` (queued|downloading|processing|complete|failed|cancelled), `downloading_since`, `error_message`, timestamps. Status is *derived* from its files.
- **`DownloadFile`** — One per mega.nz link. Fields: `url`, `name`, `status` (queued|downloading|finished|failed), `progress_bytes`, `total_bytes`, `speed`, `error_message`, `file_path`. Download aggregates these for overall progress.

### Download Engine

`MegaDownloadManager` runs an asyncio event loop in a daemon thread. The sync worker thread polls `manager.status()` every 5 seconds. Matching between download entries and `DownloadFile` records uses **three-tier matching**: (1) direct URL match with normalization, (2) `sourceUrl` match for folder downloads split into per-file entries, and (3) folder-ID match using `###n=` suffix extraction.

### Configuration

All config via `MEGAQUEUE_*` environment variables. Required at startup: `SECRET_KEY`, `PLEX_MOVIES_DIR`, `PLEX_TV_DIR`, `NTFY_TOPIC`, `DOWNLOAD_DIR`. Defaults: `POLL_INTERVAL=5`, `GRACE_PERIOD=30`, `DOWNLOAD_WORKERS=8`. Optional: `PROXY_FILE`. `unrar` must be on PATH at runtime if any download contains a `.rar` archive.

## Running

```bash
docker compose up -d        # Docker (recommended)
python run.py               # Local development
```

## Frontend conventions

Flask-Talisman sets a Content-Security-Policy whose `script-src` is `'self' https://cdn.tailwindcss.com` — it does **not** include `'unsafe-inline'`, and no nonce is configured. **All page JavaScript must therefore live in external files under `static/` and be loaded via `<script src="/static/...">`.** Inline `<script>` blocks are silently blocked by the browser (no error in the server logs, only a CSP violation in the browser console), so any feature relying on inline JS will appear to do nothing. Each page that needs JS has its own file (e.g. `static/refresh.js`, `static/logs.js`, `static/detail.js`), and the service-worker registration lives in `static/register-sw.js`.

## Testing

**Run tests:** `cd megaqueue && source .venv/bin/activate && pytest`
**Run with coverage:** `pytest --cov=megaqueue --cov-report=term-missing`
**Install deps:** `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt`

### Requirements

- Always run `pytest` after making any code changes to verify nothing is broken
- When adding new functionality, add corresponding tests
- When modifying existing behavior, update relevant tests to match
- Run the full test suite before considering a task complete

### Test Structure

```
tests/
├── conftest.py                  # Shared fixtures: db_session, app, client, sample_download
├── test_models.py               # Model creation, relationships, computed properties
├── test_migrations.py           # Named migrations idempotent against legacy DBs
├── test_mega_downloader.py      # MegaDownloadManager: status shape, start/cancel/remove
├── test_mega_urls.py            # URL normalisation, folder-ID extraction, predicates
├── test_metadata.py             # guessit parse + aggregation + confidence scoring
├── test_sync.py                 # Download engine matching, folder expansion, per-file updates
├── test_lifecycle.py            # status derivation, source-path resolution
├── test_organiser.py            # Plex-canonical paths, archive extraction (mocked)
├── test_worker.py               # Poll loop drives sync.* in order
├── test_routes.py               # Flask route responses, form handling
└── test_notifications.py        # ntfy.sh notification formatting
```

### Conventions

- **Database:** Tests use in-memory SQLite via the `db_session` fixture (conftest.py). Never use the production database.
- **HTTP mocking:** Use the `responses` library to mock external HTTP calls (ntfy.sh). Never make real HTTP requests in tests.
- **Filesystem:** Use pytest's `tmp_path` fixture for tests that need real file operations (organiser tests).
- **Flask routes:** Use the `client` fixture with `@patch("megaqueue.app.start_worker")` to avoid starting the background worker. Mock `megaqueue.app.mega_manager` for routes that call the download manager.
- **Lifecycle/sync tests:** Mock `megaqueue.lifecycle.organiser`, `megaqueue.lifecycle.notify_completion`, `megaqueue.lifecycle.notify_failure`, and `megaqueue.sync.notify_needs_review` to isolate logic from side effects.

## OpenSpec Workflow

Changes are managed through the `openspec/` directory:

- **`openspec/specs/`** — Canonical spec documents (ground truth for how the system should behave), organized by capability (data-model, download-engine, web-ui, etc.)
- **`openspec/changes/`** — Active in-progress change artifacts (proposal, design, tasks, updated specs)
- **`openspec/changes/archive/`** — Completed/archived changes

Use `/propose`, `/apply`, `/verify`, and `/archive` skills to work within this workflow. Specs are the source of truth — when implementing features, check the relevant spec in `openspec/specs/` for requirements and scenarios.

## Querying the Database

To query the database, use Python:

```bash
python -c "import sqlite3, json; conn=sqlite3.connect('megaqueue.db'); conn.row_factory=sqlite3.Row; print(json.dumps([dict(r) for r in conn.execute('SELECT * FROM downloads WHERE title LIKE \"%example%\"')], indent=2, default=str))"
```

The database is at `megaqueue.db`. The schema is defined in `megaqueue/models.py` and `megaqueue/migrations.py`.
