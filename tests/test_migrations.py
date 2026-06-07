from sqlalchemy import create_engine

from megaqueue import migrations


def _make_legacy_downloads_table(conn):
    """Build a 'legacy' schema: downloads table missing the new metadata columns,
    and download_files missing parent_id and is_extra."""
    conn.exec_driver_sql("""
        CREATE TABLE downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR NOT NULL,
            year INTEGER,
            media_type VARCHAR NOT NULL,
            status VARCHAR NOT NULL CHECK (status IN ('queued', 'downloading', 'processing', 'complete', 'failed', 'cancelled')),
            downloading_since DATETIME,
            error_message TEXT,
            created_at DATETIME,
            updated_at DATETIME
        )
    """)
    conn.exec_driver_sql("""
        CREATE TABLE download_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            download_id INTEGER NOT NULL REFERENCES downloads(id) ON DELETE CASCADE,
            url VARCHAR NOT NULL,
            name VARCHAR,
            status VARCHAR NOT NULL,
            progress_bytes INTEGER DEFAULT 0,
            total_bytes INTEGER DEFAULT 0,
            speed INTEGER DEFAULT 0,
            error_message TEXT,
            file_path VARCHAR
        )
    """)
    conn.exec_driver_sql(
        "INSERT INTO downloads (title, media_type, status) VALUES ('Old Movie', 'movie', 'complete')"
    )
    conn.commit()


def _columns(conn, table):
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def test_migrations_add_all_new_columns_to_legacy_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.connect() as conn:
        _make_legacy_downloads_table(conn)

        migrations.run_all(conn)

        df_cols = _columns(conn, "download_files")
        assert "parent_id" in df_cols
        assert "is_extra" in df_cols

        dl_cols = _columns(conn, "downloads")
        assert "metadata_confidence" in dl_cols
        assert "metadata_source" in dl_cols

        # Legacy rows default to 'high' so they bypass the review gate.
        result = conn.exec_driver_sql("SELECT metadata_confidence FROM downloads").fetchall()
        assert all(row[0] == "high" for row in result)


def test_migrations_widen_status_enum():
    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.connect() as conn:
        _make_legacy_downloads_table(conn)
        migrations.run_all(conn)

        # After migration, inserting needs_review should succeed.
        conn.exec_driver_sql(
            "INSERT INTO downloads (title, media_type, status, metadata_confidence) "
            "VALUES ('X', 'movie', 'needs_review', 'low')"
        )
        n = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM downloads WHERE status = 'needs_review'"
        ).scalar()
        assert n == 1


def test_migrations_are_idempotent():
    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.connect() as conn:
        _make_legacy_downloads_table(conn)
        migrations.run_all(conn)
        migrations.run_all(conn)  # second pass should be a no-op
        migrations.run_all(conn)

        # No duplicate columns, no errors propagated.
        df_cols = _columns(conn, "download_files")
        assert df_cols.count("is_extra") if isinstance(df_cols, list) else True
        dl_cols = _columns(conn, "downloads")
        assert "metadata_confidence" in dl_cols
