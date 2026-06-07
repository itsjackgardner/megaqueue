# MegaQueue

Python Flask app that queues mega.nz downloads via megabasterd, organizes files into Plex library folders, and sends push notifications.

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
├── sync.py             # megabasterd ↔ DB sync (matching, folder expansion, file updates)
├── lifecycle.py        # Status derivation, post-processing orchestration
├── mega_urls.py        # Pure URL helpers (normalise, extract_folder_id, is_folder_url)
├── metadata.py         # guessit-driven metadata aggregation (title/year/media_type)
├── megabasterd_client.py  # HTTP client for megabasterd REST API
├── organiser.py        # Hand-rolled organiser (movies + extras, TV episodes)
├── notifications.py    # ntfy.sh push notifications
├── static/             # JS, icons, PWA manifest
└── templates/          # Jinja2 HTML templates
run.py                  # Entrypoint: python run.py
tests/                  # pytest test suite
requirements.txt
requirements-dev.txt
```

## Running

```bash
python run.py
```

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
├── test_megabasterd_client.py   # HTTP client (mocked with `responses` library)
├── test_mega_urls.py            # URL normalisation, folder-ID extraction, predicates
├── test_metadata.py             # guessit parse + aggregation + confidence scoring
├── test_sync.py                 # megabasterd matching, folder expansion, per-file updates
├── test_lifecycle.py            # status derivation, source-path resolution
├── test_organiser.py            # Plex-canonical paths, archive extraction (mocked)
├── test_worker.py               # Poll loop drives sync.* in order
├── test_routes.py               # Flask route responses, form handling
└── test_notifications.py        # ntfy.sh notification formatting
```

### Conventions

- **Database:** Tests use in-memory SQLite via the `db_session` fixture (conftest.py). Never use the production database.
- **HTTP mocking:** Use the `responses` library to mock external HTTP calls (megabasterd API, ntfy.sh). Never make real HTTP requests in tests.
- **Filesystem:** Use pytest's `tmp_path` fixture for tests that need real file operations (organiser tests).
- **Flask routes:** Use the `client` fixture with `@patch("megaqueue.app.start_worker")` to avoid starting the background worker. Mock `megaqueue.app.mb_client` for routes that call megabasterd.
- **Lifecycle/sync tests:** Mock `megaqueue.lifecycle.organiser`, `megaqueue.lifecycle.notify_completion`, `megaqueue.lifecycle.notify_failure`, and `megaqueue.sync.notify_needs_review` to isolate logic from side effects.
