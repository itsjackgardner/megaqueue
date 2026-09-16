## ADDED Requirements

### Requirement: Application logs are persisted to SQLite
The system SHALL capture all Python log records at level INFO and above into a `log_entries` table. Each record SHALL include a timestamp, log level, module name (short form, e.g. `sync` not `megaqueue.sync`), and the formatted message string. DEBUG-level records SHALL NOT be persisted.

#### Scenario: INFO log line is persisted
- **WHEN** the sync module logs `log.info("Submitted 'Inception' to megabasterd")`
- **THEN** a row is inserted into `log_entries` with `level="INFO"`, `module="sync"`, and the formatted message

#### Scenario: DEBUG log line is not persisted
- **WHEN** the megabasterd_client module logs `log.debug("Download not found in megabasterd")`
- **THEN** no row is inserted into `log_entries`

#### Scenario: WARNING and ERROR are persisted
- **WHEN** the worker module logs `log.error("Worker poll error: connection refused")`
- **THEN** a row is inserted with `level="ERROR"` and `module="worker"`

### Requirement: Log entries are streamed to the browser via SSE
The system SHALL provide an SSE endpoint at `GET /api/logs/stream` that pushes each new log entry to connected clients as a JSON-encoded Server-Sent Event. The event data SHALL include `timestamp`, `level`, `module`, and `message` fields. Multiple concurrent browser tabs SHALL each receive all entries independently.

#### Scenario: Browser receives live log entry
- **WHEN** a browser has an open `EventSource` connection to `/api/logs/stream` and a new INFO log line is emitted
- **THEN** the browser receives an SSE event with the log entry as JSON data

#### Scenario: Multiple tabs receive the same entry
- **WHEN** two browser tabs are connected to `/api/logs/stream` and a log line is emitted
- **THEN** both tabs receive the same event independently

#### Scenario: Disconnected client does not block logging
- **WHEN** a browser tab disconnects from the SSE endpoint
- **THEN** the logging handler removes that client's queue and continues operating normally

### Requirement: Recent log history is available via REST
The system SHALL provide a JSON endpoint at `GET /api/logs` that returns the most recent log entries from the database, ordered newest-first. The endpoint SHALL accept an optional `limit` query parameter (default 200, max 1000).

#### Scenario: Fetch recent log history
- **WHEN** a client requests `GET /api/logs`
- **THEN** the response is a JSON array of the 200 most recent log entries, each with `id`, `timestamp`, `level`, `module`, and `message`

#### Scenario: Custom limit
- **WHEN** a client requests `GET /api/logs?limit=50`
- **THEN** the response contains at most 50 entries

### Requirement: Logs page displays a colour-coded live tail
The system SHALL provide a `/logs` page accessible from the main navigation. The page SHALL display log entries in chronological order with each entry showing timestamp, module name, and message. Module names SHALL be colour-coded with a consistent colour per module. The page SHALL provide filter chips to show/hide entries by module.

#### Scenario: Page loads with recent history
- **WHEN** the user navigates to `/logs`
- **THEN** the page displays the most recent 200 log entries fetched from the API, with live streaming active

#### Scenario: New entries appear in real time
- **WHEN** the user is viewing `/logs` and a new log line is emitted
- **THEN** the entry appears at the bottom of the log list without a page refresh

#### Scenario: Auto-scroll follows new entries
- **WHEN** the user is scrolled to the bottom of the log list and new entries arrive
- **THEN** the view auto-scrolls to show the latest entry

#### Scenario: Scrolling up pauses auto-scroll
- **WHEN** the user scrolls up to read older entries and new entries arrive
- **THEN** auto-scroll is paused and the view stays at the user's current position

#### Scenario: Module filter chips toggle visibility
- **WHEN** the user clicks a module filter chip (e.g. "sync")
- **THEN** entries from that module are hidden, and clicking again restores them

#### Scenario: Module names are colour-coded
- **WHEN** log entries are displayed
- **THEN** each module name is rendered in a distinct, consistent colour (e.g. sync=blue, metadata=purple, organiser=green, worker=gray, lifecycle=orange, notify=teal, app=white)

### Requirement: Log messages are clean and user-readable
All INFO-level log messages emitted by the application SHALL be written for a non-developer audience viewing them in the UI. Messages SHALL NOT contain raw database IDs, Python tracebacks, or internal object representations. Messages SHALL use the download title as the primary identifier. Error-level messages MAY include technical detail (exception messages) since they're diagnostic by nature.

#### Scenario: Metadata resolution is logged
- **WHEN** the metadata module resolves a download's metadata via guessit
- **THEN** an INFO log line is emitted with the resolved title, media type, and confidence level (e.g. "Resolved 'Inception' as movie (2010), confidence high")

#### Scenario: Notification success is logged
- **WHEN** a push notification is sent successfully via ntfy.sh
- **THEN** an INFO log line is emitted (e.g. "Push notification sent: Inception complete")

#### Scenario: Lifecycle post-processing start is logged
- **WHEN** post-processing begins for a download
- **THEN** an INFO log line is emitted (e.g. "Post-processing started for 'Inception'")

#### Scenario: Existing messages do not contain raw IDs
- **WHEN** any INFO-level log message references a download
- **THEN** the message uses the download's title, not its database ID
