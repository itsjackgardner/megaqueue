## ADDED Requirements

### Requirement: Add missing columns to existing tables on startup
The system SHALL check for missing columns in existing SQLite tables during `setupSqliteTables()` and add them using `ALTER TABLE ADD COLUMN` if they are absent.

#### Scenario: Downloads table missing createdAt column
- **WHEN** `setupSqliteTables()` runs and the `downloads` table exists without a `createdAt` column
- **THEN** the system SHALL execute `ALTER TABLE downloads ADD COLUMN createdAt BIG INT` to add the column

#### Scenario: Downloads table already has createdAt column
- **WHEN** `setupSqliteTables()` runs and the `downloads` table already contains the `createdAt` column
- **THEN** the system SHALL skip the ALTER and continue without error

#### Scenario: Fresh database with no existing tables
- **WHEN** `setupSqliteTables()` runs on a new database with no tables
- **THEN** the `CREATE TABLE IF NOT EXISTS` statements SHALL create all tables with the `createdAt` column included, and the migration check SHALL be a no-op

### Requirement: Column existence check uses PRAGMA table_info
The system SHALL determine column existence by querying `PRAGMA table_info(<table>)` and checking the result set for the target column name.

#### Scenario: PRAGMA returns column list
- **WHEN** the system queries `PRAGMA table_info(downloads)`
- **THEN** it SHALL iterate the result set and return true if any row's `name` field matches the target column name
