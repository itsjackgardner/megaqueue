## Why

The only way to see what MegaQueue is doing is to watch the terminal running `python run.py`. When a download fails overnight or the organiser makes a surprising decision, there's no way to find out what happened without SSH-ing into the NUC and scrolling through stdout. A Plex-style log viewer in the web UI would make the system observable from the phone — live tail for watching in-progress work, and persistent history for diagnosing past events.

## What Changes

- Add a `log_entries` table to persist application log lines (INFO and above) to SQLite
- Add a custom Python logging handler that writes to the DB and fans out to SSE clients
- Add an SSE endpoint (`/api/logs/stream`) for live-tailing new log entries
- Add a GET endpoint (`/api/logs`) for fetching recent history
- Add a `/logs` page with auto-scrolling live tail, module colour-coding, and per-module filter chips
- Add the logs page as a proper nav item in the base template
- Clean up existing log messages for UI readability (remove raw IDs, developer jargon)
- Add missing log lines in modules that currently operate silently (metadata, notifications success, lifecycle start)
- Establish a convention: INFO+ goes to UI, DEBUG stays terminal-only

## Capabilities

### New Capabilities
- `log-viewer`: In-browser log tail and history — DB-backed log storage, SSE streaming, the `/logs` page UI, and the logging infrastructure (handler, endpoints)

### Modified Capabilities
- `web-ui`: Adding `/logs` route and nav item to the base template
- `data-model`: Adding `log_entries` table schema

## Impact

- **New files**: `megaqueue/log_handler.py` (custom handler + SSE fan-out), `megaqueue/templates/logs.html`
- **Modified files**: `models.py` (LogEntry model), `migrations.py` (new migration), `app.py` (new routes, nav context, handler setup), `base.html` (nav item), plus log-line edits across `sync.py`, `metadata.py`, `organiser.py`, `lifecycle.py`, `notifications.py`
- **Dependencies**: None new — SSE is native HTTP, `collections.deque` and `queue.Queue` are stdlib
- **DB**: One new table, low write volume (~20-50 rows per download lifecycle)
