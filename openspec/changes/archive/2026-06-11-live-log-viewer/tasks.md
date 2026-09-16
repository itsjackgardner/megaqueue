## 1. Data Model & Migration

- [x] 1.1 Add `LogEntry` model to `models.py` (id, timestamp, level, module, message)
- [x] 1.2 Add migration in `migrations.py` to create `log_entries` table (idempotent)

## 2. Logging Infrastructure

- [x] 2.1 Create `log_handler.py` with `DBLogHandler` — writes INFO+ records to `log_entries`, strips `megaqueue.` prefix from logger names
- [x] 2.2 Add SSE fan-out to `DBLogHandler` — maintain a set of `SimpleQueue` per connected client, push serialised entries on each log record, remove on disconnect
- [x] 2.3 Wire up `DBLogHandler` in `create_app()` — attach to root `megaqueue` logger so all submodule loggers inherit it

## 3. API Endpoints

- [x] 3.1 Add `GET /api/logs` endpoint — return last 200 log entries as JSON (support `limit` query param, max 1000)
- [x] 3.2 Add `GET /api/logs/stream` SSE endpoint — yield new log entries as JSON events from the client's queue
- [x] 3.3 Update CSP to allow `connect-src 'self'` for EventSource connections

## 4. Logs Page UI

- [x] 4.1 Create `templates/logs.html` — log list container, module colour-coding, timestamp + module + message per row
- [x] 4.2 Add JavaScript: fetch `/api/logs` on page load, populate initial entries
- [x] 4.3 Add JavaScript: open `EventSource` to `/api/logs/stream`, append new entries live
- [x] 4.4 Add auto-scroll behaviour — follow tail when at bottom, pause when user scrolls up
- [x] 4.5 Add module filter chips — toggle visibility per module, colour-coded to match log entries
- [x] 4.6 Add `/logs` nav item to `base.html`

## 5. Log Hygiene

- [x] 5.1 Add missing log lines: `metadata.py` — log resolution results (title, type, year, confidence)
- [x] 5.2 Add missing log lines: `notifications.py` — log success, not just failure
- [x] 5.3 Add missing log lines: `lifecycle.py` — log post-processing start
- [x] 5.4 Add missing log lines: `organiser.py` — log archive extraction start
- [x] 5.5 Clean up existing messages: remove raw DB IDs from `app.py` and `sync.py`, reword developer-isms (e.g. "child DownloadFile records" → "files")

## 6. Tests

- [x] 6.1 Test `LogEntry` model creation and ordering
- [x] 6.2 Test `DBLogHandler` writes INFO+ to DB, skips DEBUG
- [x] 6.3 Test `GET /api/logs` returns entries with correct format and limit
- [x] 6.4 Test SSE fan-out: handler pushes to client queues, cleans up on disconnect
- [x] 6.5 Test migration is idempotent (run twice without error)
- [x] 6.6 Test log hygiene: verify key modules emit expected INFO lines during typical flows
