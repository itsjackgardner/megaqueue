## ADDED Requirements

### Requirement: LogEntry entity stores application log records
The system SHALL persist a LogEntry entity with fields: id (integer primary key, auto-increment), timestamp (datetime, not null), level (text, not null — one of INFO, WARNING, ERROR), module (text, not null — short module name e.g. "sync", "worker"), and message (text, not null). The table SHALL be named `log_entries`.

#### Scenario: LogEntry is created from a Python log record
- **WHEN** the logging handler processes an INFO-level record from `megaqueue.sync`
- **THEN** a LogEntry row is inserted with the current timestamp, `level="INFO"`, `module="sync"`, and the formatted message text

#### Scenario: LogEntry records are ordered by timestamp
- **WHEN** multiple log entries are queried
- **THEN** they can be ordered by `timestamp` and `id` to produce a chronological sequence

### Requirement: Database migration creates log_entries table
The system SHALL add a migration in `migrations.py` that creates the `log_entries` table when starting against an existing database. The migration SHALL be idempotent — running against a database that already has the table SHALL succeed without error.

#### Scenario: Fresh database gets the table
- **WHEN** the application starts against a database without `log_entries`
- **THEN** the migration creates the table with the schema defined above

#### Scenario: Migration is idempotent
- **WHEN** the application restarts against a database that already has `log_entries`
- **THEN** the migration runs safely without error and no data is altered
