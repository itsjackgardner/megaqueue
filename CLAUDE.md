# MegaQueue

Python Flask app that queues mega.nz downloads via megabasterd, organizes files into Plex library folders, and sends push notifications.

## Project Structure

```
megaqueue/              # Package directory (all source code)
├── __init__.py
├── app.py              # Flask app, routes, startup validation
├── config.py           # All config via MEGAQUEUE_* env vars
├── models.py           # SQLAlchemy models (Download, DownloadFile)
├── worker.py           # Background thread — polls megabasterd, updates DB
├── megabasterd_client.py  # HTTP client for megabasterd REST API
├── filebot_organizer.py   # FileBot-based file organization into Plex folders
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
├── test_megabasterd_client.py   # HTTP client (mocked with `responses` library)
├── test_worker.py               # URL normalization, file matching, status derivation
├── test_filebot_organizer.py    # FileBot file routing, archive detection, cleanup (uses tmp_path)
├── test_routes.py               # Flask route responses, form handling
└── test_notifications.py        # ntfy.sh notification formatting
```

### Conventions

- **Database:** Tests use in-memory SQLite via the `db_session` fixture (conftest.py). Never use the production database.
- **HTTP mocking:** Use the `responses` library to mock external HTTP calls (megabasterd API, ntfy.sh). Never make real HTTP requests in tests.
- **Filesystem:** Use pytest's `tmp_path` fixture for tests that need real file operations (organizer tests).
- **Flask routes:** Use the `client` fixture with `@patch("megaqueue.app.start_worker")` to avoid starting the background worker. Mock `megaqueue.app.mb_client` for routes that call megabasterd.
- **Worker tests:** Mock `megaqueue.worker.filebot_organizer`, `megaqueue.worker.notify_completion`, and `megaqueue.worker.notify_failure` to isolate worker logic from side effects.
