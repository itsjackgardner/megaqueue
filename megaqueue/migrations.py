"""Database migrations registered as named, ordered functions.

Each migration takes a SQLAlchemy connection and runs one or more `ALTER TABLE`
statements. Migrations MUST be idempotent: if a column already exists or a
schema change has already been applied, the function should swallow the error
and log at debug level. This is the pragmatic equivalent of Alembic for a
single-user SQLite app.
"""

import logging

log = logging.getLogger(__name__)


def _add_parent_id_column(conn):
    conn.exec_driver_sql(
        "ALTER TABLE download_files ADD COLUMN parent_id INTEGER REFERENCES download_files(id)"
    )


def _add_metadata_confidence_column(conn):
    conn.exec_driver_sql(
        "ALTER TABLE downloads ADD COLUMN metadata_confidence TEXT NOT NULL DEFAULT 'high'"
    )


def _add_metadata_source_column(conn):
    conn.exec_driver_sql(
        "ALTER TABLE downloads ADD COLUMN metadata_source TEXT"
    )


def _add_is_extra_column(conn):
    conn.exec_driver_sql(
        "ALTER TABLE download_files ADD COLUMN is_extra BOOLEAN NOT NULL DEFAULT 0"
    )


_NEW_DOWNLOADS_DDL = """
    CREATE TABLE downloads_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title VARCHAR,
        year INTEGER,
        media_type VARCHAR CHECK (media_type IN ('movie', 'tv')),
        status VARCHAR NOT NULL CHECK (status IN ('queued', 'downloading', 'needs_review', 'processing', 'complete', 'failed', 'cancelled')),
        downloading_since DATETIME,
        error_message TEXT,
        metadata_confidence VARCHAR NOT NULL DEFAULT 'high' CHECK (metadata_confidence IN ('high', 'low')),
        metadata_source VARCHAR CHECK (metadata_source IN ('guessit', 'user')),
        created_at DATETIME,
        updated_at DATETIME
    )
"""


def _widen_status_enum(conn):
    """Rebuild the downloads table to widen the status CHECK to include needs_review.

    SQLite cannot ALTER a CHECK constraint in place, so we rebuild via the
    standard create-new / copy / swap pattern. Names columns explicitly so
    column-order differences between legacy and new schema don't shuffle data.

    Idempotent: if the CHECK already accepts needs_review, the new table is
    rebuilt anyway; it's the same shape and the copy is loss-free.
    """
    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    conn.exec_driver_sql("DROP TABLE IF EXISTS downloads_new")
    conn.exec_driver_sql(_NEW_DOWNLOADS_DDL)
    conn.exec_driver_sql("""
        INSERT INTO downloads_new (
            id, title, year, media_type, status, downloading_since,
            error_message, metadata_confidence, metadata_source,
            created_at, updated_at
        )
        SELECT
            id, title, year, media_type, status, downloading_since,
            error_message,
            COALESCE(metadata_confidence, 'high') AS metadata_confidence,
            metadata_source,
            created_at, updated_at
        FROM downloads
    """)
    conn.exec_driver_sql("DROP TABLE downloads")
    conn.exec_driver_sql("ALTER TABLE downloads_new RENAME TO downloads")
    conn.exec_driver_sql("PRAGMA foreign_keys=ON")


MIGRATIONS = [
    ("add_parent_id_column", _add_parent_id_column),
    ("add_metadata_confidence_column", _add_metadata_confidence_column),
    ("add_metadata_source_column", _add_metadata_source_column),
    ("add_is_extra_column", _add_is_extra_column),
    ("widen_status_enum", _widen_status_enum),
]


def run_all(conn):
    """Run every registered migration in order. Each is wrapped to be idempotent."""
    for name, fn in MIGRATIONS:
        try:
            fn(conn)
            log.info("Migration %s applied", name)
        except Exception as e:
            log.debug("Migration %s skipped: %s", name, e)
    conn.commit()
