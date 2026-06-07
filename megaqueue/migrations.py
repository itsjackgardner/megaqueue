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


MIGRATIONS = [
    ("add_parent_id_column", _add_parent_id_column),
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
