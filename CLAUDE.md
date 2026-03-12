# MegaQueue

Python Flask app that queues mega.nz downloads via megabasterd, organizes files into Plex library folders, and sends push notifications.

## Testing

**Run tests:** `cd megaqueue && source .venv/bin/activate && pytest`
**Run with coverage:** `cd megaqueue && source .venv/bin/activate && pytest --cov=. --cov-report=term-missing`
**Install deps:** `cd megaqueue && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt`

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
├── test_organizer.py            # File routing, archive detection, cleanup (uses tmp_path)
├── test_routes.py               # Flask route responses, form handling
└── test_notifications.py        # ntfy.sh notification formatting
```

### Conventions

- **Database:** Tests use in-memory SQLite via the `db_session` fixture (conftest.py). Never use the production database.
- **HTTP mocking:** Use the `responses` library to mock external HTTP calls (megabasterd API, ntfy.sh). Never make real HTTP requests in tests.
- **Filesystem:** Use pytest's `tmp_path` fixture for tests that need real file operations (organizer tests).
- **Flask routes:** Use the `client` fixture with `@patch("app.start_worker")` to avoid starting the background worker. Mock `app.mb_client` for routes that call megabasterd.
- **Worker tests:** Mock `worker.organize_download`, `worker.notify_completion`, and `worker.notify_failure` to isolate worker logic from side effects.
