## Why

MegaBasterd's SQLite database uses `CREATE TABLE IF NOT EXISTS` to initialize the `downloads` table. The `createdAt` column was added to the schema after initial deployment, but existing databases never receive the new column because the CREATE statement is a no-op when the table already exists. This causes `[SQLITE_ERROR] SQL error or missing database (table downloads has no column named createdAt)` when registering new downloads.

## What Changes

- Add a schema migration step in `DBTools.setupSqliteTables()` that uses `ALTER TABLE ... ADD COLUMN` to add `createdAt` to existing `downloads` tables that are missing it
- The migration must be idempotent (safe to run multiple times) since SQLite doesn't support `ADD COLUMN IF NOT EXISTS`

## Capabilities

### New Capabilities

- `db-schema-migration`: Adds missing columns to existing SQLite tables during startup, ensuring schema compatibility after upgrades

### Modified Capabilities

None.

## Impact

- `megabasterd/src/main/java/com/tonikelope/megabasterd/DBTools.java` — `setupSqliteTables()` method
- Existing MegaBasterd installations with pre-`createdAt` databases will self-heal on next startup
