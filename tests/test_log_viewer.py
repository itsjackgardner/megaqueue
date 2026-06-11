import logging
from datetime import datetime
from queue import SimpleQueue
from unittest.mock import patch

from sqlalchemy import create_engine

from megaqueue import migrations
from megaqueue.models import LogEntry


# --- 6.1: LogEntry model creation and ordering ---

def test_log_entry_creation(db_session):
    entry = LogEntry(
        timestamp=datetime(2026, 6, 11, 12, 0, 0),
        level="INFO",
        module="sync",
        message="Submitted 'Inception' to megabasterd",
    )
    db_session.add(entry)
    db_session.commit()

    assert entry.id is not None
    assert entry.level == "INFO"
    assert entry.module == "sync"


def test_log_entry_ordering(db_session):
    e1 = LogEntry(timestamp=datetime(2026, 6, 11, 12, 0, 0),
                  level="INFO", module="sync", message="First")
    e2 = LogEntry(timestamp=datetime(2026, 6, 11, 12, 0, 1),
                  level="INFO", module="worker", message="Second")
    e3 = LogEntry(timestamp=datetime(2026, 6, 11, 12, 0, 2),
                  level="WARNING", module="sync", message="Third")
    db_session.add_all([e1, e2, e3])
    db_session.commit()

    entries = db_session.query(LogEntry).order_by(LogEntry.id).all()
    assert [e.message for e in entries] == ["First", "Second", "Third"]


# --- 6.2: DBLogHandler writes INFO+ to DB, skips DEBUG ---

def test_db_log_handler_writes_info(db_session):
    from megaqueue.log_handler import DBLogHandler

    handler = DBLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = logging.LogRecord(
        name="megaqueue.sync", level=logging.INFO, pathname="",
        lineno=0, msg="Test info message", args=(), exc_info=None,
    )
    handler.emit(record)

    entries = db_session.query(LogEntry).all()
    assert len(entries) == 1
    assert entries[0].level == "INFO"
    assert entries[0].module == "sync"
    assert entries[0].message == "Test info message"


def test_db_log_handler_writes_warning(db_session):
    from megaqueue.log_handler import DBLogHandler

    handler = DBLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = logging.LogRecord(
        name="megaqueue.worker", level=logging.WARNING, pathname="",
        lineno=0, msg="Test warning", args=(), exc_info=None,
    )
    handler.emit(record)

    entries = db_session.query(LogEntry).all()
    assert len(entries) == 1
    assert entries[0].level == "WARNING"


def test_db_log_handler_skips_debug(db_session):
    from megaqueue.log_handler import DBLogHandler

    handler = DBLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = logging.LogRecord(
        name="megaqueue.sync", level=logging.DEBUG, pathname="",
        lineno=0, msg="Debug noise", args=(), exc_info=None,
    )
    handler.emit(record)

    entries = db_session.query(LogEntry).all()
    assert len(entries) == 0


def test_db_log_handler_strips_megaqueue_prefix(db_session):
    from megaqueue.log_handler import DBLogHandler

    handler = DBLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = logging.LogRecord(
        name="megaqueue.organiser", level=logging.INFO, pathname="",
        lineno=0, msg="Moved file", args=(), exc_info=None,
    )
    handler.emit(record)

    entry = db_session.query(LogEntry).first()
    assert entry.module == "organiser"


# --- 6.3: GET /api/logs ---

@patch("megaqueue.app.start_worker")
def test_api_logs_returns_entries(mock_worker, client, db_session):
    for i in range(5):
        db_session.add(LogEntry(
            timestamp=datetime(2026, 6, 11, 12, 0, i),
            level="INFO", module="sync", message=f"Entry {i}",
        ))
    db_session.commit()

    resp = client.get("/api/logs")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 5
    assert data[0]["message"] == "Entry 0"
    assert data[4]["message"] == "Entry 4"
    assert "id" in data[0]
    assert "timestamp" in data[0]
    assert "level" in data[0]
    assert "module" in data[0]


@patch("megaqueue.app.start_worker")
def test_api_logs_respects_limit(mock_worker, client, db_session):
    for i in range(10):
        db_session.add(LogEntry(
            timestamp=datetime(2026, 6, 11, 12, 0, i),
            level="INFO", module="sync", message=f"Entry {i}",
        ))
    db_session.commit()

    resp = client.get("/api/logs?limit=3")
    data = resp.get_json()
    assert len(data) == 3
    assert data[0]["message"] == "Entry 7"
    assert data[2]["message"] == "Entry 9"


@patch("megaqueue.app.start_worker")
def test_api_logs_caps_limit_at_1000(mock_worker, client, db_session):
    resp = client.get("/api/logs?limit=9999")
    assert resp.status_code == 200


# --- 6.4: SSE fan-out ---

def test_sse_subscribe_and_push():
    from megaqueue.log_handler import DBLogHandler

    handler = DBLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    q = handler.subscribe()

    record = logging.LogRecord(
        name="megaqueue.sync", level=logging.INFO, pathname="",
        lineno=0, msg="SSE test", args=(), exc_info=None,
    )
    handler.emit(record)

    event = q.get(timeout=1)
    assert "SSE test" in event
    assert "sync" in event

    handler.unsubscribe(q)


def test_sse_unsubscribe_removes_client():
    from megaqueue.log_handler import DBLogHandler

    handler = DBLogHandler()
    q = handler.subscribe()
    assert len(handler._clients) == 1

    handler.unsubscribe(q)
    assert len(handler._clients) == 0


def test_sse_multiple_clients_receive_same_event():
    from megaqueue.log_handler import DBLogHandler

    handler = DBLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    q1 = handler.subscribe()
    q2 = handler.subscribe()

    record = logging.LogRecord(
        name="megaqueue.worker", level=logging.INFO, pathname="",
        lineno=0, msg="Broadcast", args=(), exc_info=None,
    )
    handler.emit(record)

    e1 = q1.get(timeout=1)
    e2 = q2.get(timeout=1)
    assert "Broadcast" in e1
    assert "Broadcast" in e2

    handler.unsubscribe(q1)
    handler.unsubscribe(q2)


# --- 6.5: Migration idempotency ---

def _columns(conn, table):
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _tables(conn):
    rows = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def test_log_entries_migration_creates_table():
    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.connect() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE downloads (
                id INTEGER PRIMARY KEY, title VARCHAR, year INTEGER,
                media_type VARCHAR, status VARCHAR NOT NULL,
                downloading_since DATETIME, error_message TEXT,
                created_at DATETIME, updated_at DATETIME
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE download_files (
                id INTEGER PRIMARY KEY,
                download_id INTEGER NOT NULL REFERENCES downloads(id),
                url VARCHAR NOT NULL, name VARCHAR,
                status VARCHAR NOT NULL,
                progress_bytes INTEGER DEFAULT 0,
                total_bytes INTEGER DEFAULT 0,
                speed INTEGER DEFAULT 0,
                error_message TEXT, file_path VARCHAR
            )
        """)
        conn.commit()

        migrations.run_all(conn)

        assert "log_entries" in _tables(conn)
        cols = _columns(conn, "log_entries")
        assert cols == {"id", "timestamp", "level", "module", "message"}


def test_log_entries_migration_is_idempotent():
    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.connect() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE downloads (
                id INTEGER PRIMARY KEY, title VARCHAR, year INTEGER,
                media_type VARCHAR, status VARCHAR NOT NULL,
                downloading_since DATETIME, error_message TEXT,
                created_at DATETIME, updated_at DATETIME
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE download_files (
                id INTEGER PRIMARY KEY,
                download_id INTEGER NOT NULL REFERENCES downloads(id),
                url VARCHAR NOT NULL, name VARCHAR,
                status VARCHAR NOT NULL,
                progress_bytes INTEGER DEFAULT 0,
                total_bytes INTEGER DEFAULT 0,
                speed INTEGER DEFAULT 0,
                error_message TEXT, file_path VARCHAR
            )
        """)
        conn.commit()

        migrations.run_all(conn)
        migrations.run_all(conn)

        assert "log_entries" in _tables(conn)


# --- 6.6: Log hygiene ---

def test_metadata_refresh_logs_resolution(db_session):
    from megaqueue.enums import DownloadStatus, FileStatus, MediaType
    from megaqueue.models import Download, DownloadFile

    dl = Download(title=None, media_type=None, status=DownloadStatus.DOWNLOADING)
    dl.files.append(DownloadFile(
        url="u1", name="Inception.2010.1080p.mkv",
        status=FileStatus.DOWNLOADING, total_bytes=1000,
    ))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.metadata.log") as mock_log:
        from megaqueue.metadata import refresh
        refresh(dl)
        mock_log.info.assert_called()
        call_args = mock_log.info.call_args[0]
        assert "Inception" in str(call_args)


def test_notification_logs_success():
    from megaqueue.models import Download

    dl = Download(title="Test Movie", year=2024)

    with patch("megaqueue.notifications.requests") as mock_req, \
         patch("megaqueue.notifications.log") as mock_log:
        mock_req.post.return_value = None
        from megaqueue.notifications import notify_completion
        notify_completion(dl)
        mock_log.info.assert_called_once()
        assert "Push notification sent" in mock_log.info.call_args[0][0]


def test_lifecycle_logs_post_processing_start(db_session):
    from megaqueue.enums import DownloadStatus, FileStatus
    from megaqueue.models import Download, DownloadFile

    dl = Download(title="Test", media_type="movie", year=2024,
                  status=DownloadStatus.PROCESSING)
    dl.files.append(DownloadFile(url="u1", name="test.mkv", status=FileStatus.FINISHED))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.lifecycle.log") as mock_log, \
         patch("megaqueue.lifecycle.organiser") as mock_org, \
         patch("megaqueue.lifecycle.notify_completion"):
        mock_org.organize_download.return_value = ["/dest/test.mkv"]
        from megaqueue.lifecycle import post_process
        post_process(dl, None)
        info_calls = [str(c) for c in mock_log.info.call_args_list]
        assert any("Post-processing started" in c for c in info_calls)
