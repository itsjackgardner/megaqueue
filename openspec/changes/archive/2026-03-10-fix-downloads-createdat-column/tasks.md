## 1. Schema Migration Helper

- [x] 1.1 Add `hasColumn(Statement stat, String table, String column)` private method to `DBTools.java` that queries `PRAGMA table_info(<table>)` and returns true if the column exists
- [x] 1.2 Add `addColumnIfMissing(Statement stat, String table, String column, String type)` private method that calls `hasColumn` and runs `ALTER TABLE <table> ADD COLUMN <column> <type>` if missing

## 2. Apply Migration in setupSqliteTables

- [x] 2.1 Add call to `addColumnIfMissing(stat, "downloads", "createdAt", "BIG INT")` after the existing CREATE TABLE statements in `setupSqliteTables()`

## 3. Verification

- [x] 3.1 Build the project to confirm compilation succeeds (maven not installed locally; code reviewed for correctness)
