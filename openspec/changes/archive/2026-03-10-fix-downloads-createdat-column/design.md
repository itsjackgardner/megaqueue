## Context

MegaBasterd uses SQLite for persisting downloads, uploads, and settings. The schema is initialized via `CREATE TABLE IF NOT EXISTS` statements in `DBTools.setupSqliteTables()`. The `createdAt` column was added to the `downloads` table definition, but `CREATE TABLE IF NOT EXISTS` is a no-op for existing tables — it never alters them. Deployed instances with pre-existing databases hit a runtime error when `insertDownload()` tries to write to the missing column.

## Goals / Non-Goals

**Goals:**
- Existing databases automatically gain the `createdAt` column on next startup
- Migration is idempotent — safe to run on every startup, whether the column exists or not
- Zero data loss — existing download rows are preserved

**Non-Goals:**
- Building a general-purpose migration framework
- Backfilling `createdAt` values for existing rows (NULL is acceptable for historical data)

## Decisions

**Use `ALTER TABLE ADD COLUMN` with error handling instead of schema introspection**

SQLite doesn't support `ADD COLUMN IF NOT EXISTS`. Two options:
1. Query `PRAGMA table_info(downloads)` to check if `createdAt` exists, then ALTER if missing
2. Attempt `ALTER TABLE downloads ADD COLUMN createdAt BIG INT` and catch the "duplicate column" error

Option 1 is cleaner — it avoids relying on exception handling for control flow and makes the intent explicit. We'll add a helper method that checks for column existence via `PRAGMA table_info` and conditionally runs the ALTER.

## Risks / Trade-offs

- [Risk] Future schema changes will need similar migration logic → Keep the helper generic (`addColumnIfNotMissing`) so it can be reused
- [Risk] `PRAGMA table_info` behavior could vary across SQLite versions → This pragma has been stable since SQLite 3.0; MegaBasterd's bundled JDBC driver includes a compatible version
