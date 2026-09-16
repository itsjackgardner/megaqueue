## Context

MegaQueue is a self-hosted download manager running on a Windows NUC. The web UI is server-rendered Jinja2/Tailwind served by Flask. The only observability today is the terminal running `python run.py` — there's no way to see what happened (or is happening) from the phone browser. Every module uses Python's `logging.getLogger(__name__)` but output only goes to stderr.

The codebase has ~25 log lines across 9 modules. Some modules (metadata, notifications on success, lifecycle start) are completely silent. Existing messages are a mix of user-friendly and developer-oriented.

## Goals / Non-Goals

**Goals:**
- Persist INFO+ log entries to SQLite so history survives restarts
- Stream new entries to the browser in real time via SSE
- Provide a `/logs` page with module colour-coding, filter chips, and auto-scrolling live tail
- Clean up existing log messages for UI readability and add missing log lines in silent modules
- Establish a clear convention: INFO+ is user-facing (UI + terminal), DEBUG is terminal-only

**Non-Goals:**
- Per-download activity timeline (possible future enhancement, but not this change)
- Log retention management / pruning (volume is low enough that it's not a concern yet)
- Log search / full-text filtering (simple module filter chips are sufficient)
- Authentication on the log endpoint (the app already sits behind Cloudflare Access)

## Decisions

### 1. Storage: SQLite table, not in-memory ring buffer

**Decision:** Persist log entries to a `log_entries` table in the existing SQLite database.

**Alternatives:**
- *In-memory `deque`*: Simpler, but loses history on restart. The main use case ("what happened overnight?") requires persistence.
- *Log file + tail*: Would need file rotation, parsing, and the SSE fan-out is harder to wire up.

**Rationale:** Volume is tiny (~20-50 INFO+ lines per download lifecycle). SQLite handles this without breaking a sweat, and we already have the DB + migrations infrastructure.

### 2. Transport: Server-Sent Events (SSE), not WebSocket

**Decision:** Use SSE via a Flask generator endpoint for live streaming.

**Alternatives:**
- *WebSocket*: Bidirectional, but we only need server→client. Requires a library (flask-sock or similar) and complicates the deployment.
- *Polling*: Simple but wastes bandwidth and adds latency. Defeats the "live tail" feel.

**Rationale:** SSE is HTTP-native, works with Flask's built-in streaming response, needs zero dependencies, and `EventSource` in the browser is ~5 lines of JS. One-way push is exactly the right model.

### 3. Fan-out: Queue per SSE client, fed by the logging handler

**Decision:** The custom logging handler maintains a set of `queue.SimpleQueue` instances — one per connected SSE client. On each log record, the handler writes to the DB and pushes a serialised entry to every connected client's queue. The SSE generator reads from its queue and yields events.

**Rationale:** This is the standard pattern for SSE fan-out in threaded Python apps. `SimpleQueue` is thread-safe without explicit locking. Client disconnects are detected when the generator exits and the queue is removed from the set.

### 4. Log level threshold: INFO+ to UI, DEBUG to terminal only

**Decision:** The DB handler only captures INFO, WARNING, and ERROR. DEBUG stays on the stderr StreamHandler only.

**Rationale:** DEBUG output (guessit raw results, megabasterd API response bodies, matching internals) is noisy and only useful when actively debugging on the box. The UI should show meaningful events, not implementation noise.

### 5. Module names: short canonical labels, not Python module paths

**Decision:** Map `megaqueue.sync` → `sync`, `megaqueue.organiser` → `organiser`, etc. The handler strips the `megaqueue.` prefix. The UI colour map uses these short names.

**Rationale:** `megaqueue.sync` is noise in the UI. Users think in terms of "sync", "metadata", "organiser".

### 6. Log hygiene: clean up before shipping

**Decision:** As part of this change, audit and update all existing log lines:
- Remove raw database IDs from messages (e.g., `download %d` → just use title)
- Add missing log lines: metadata resolution results, notification success, lifecycle post-processing start, organiser archive extraction
- Reword developer-oriented messages for clarity (e.g., "Expanded folder '%s' into %d child DownloadFile records" → "Expanded folder into %d files")

### 7. Page load: fetch history from DB, then switch to SSE

**Decision:** `/logs` page loads with an initial batch of recent entries (last 200) fetched via `GET /api/logs`. JavaScript then opens an `EventSource` to `/api/logs/stream` for live updates. New entries append at the bottom. Auto-scroll is active when the user is at the bottom; scrolling up pauses it.

## Risks / Trade-offs

**[Risk] SQLite write contention from logging handler** → The handler runs on the worker thread (which does most logging) and occasionally the Flask request thread. SQLite's WAL mode (already in use) handles this fine at the volume we're talking about. If it ever became an issue, we could batch writes, but it won't.

**[Risk] SSE connections held open by the Flask dev server** → Flask's dev server is single-threaded by default, but MegaQueue already runs with `threaded=True` for the worker. SSE connections are lightweight (one thread per connected browser tab). With 1-2 concurrent viewers this is a non-issue.

**[Risk] Log message quality is subjective** → The log hygiene pass may need iteration. Starting with a clear convention (INFO = "a user would understand this") and adjusting based on real use is the right approach.

**[Trade-off] No log retention policy** → The table will grow indefinitely. At ~100-200 rows/day, that's ~70k rows/year — trivial for SQLite. Can add a cleanup job later if needed.
