import os

# Set test config before any app modules are imported
os.environ.update({
    "MEGAQUEUE_SECRET_KEY": "test-secret-key",
    "MEGAQUEUE_PLEX_MOVIES_DIR": "/tmp/test-plex-movies",
    "MEGAQUEUE_PLEX_TV_DIR": "/tmp/test-plex-tv",
    "MEGAQUEUE_MEGABASTERD_DOWNLOAD_DIR": "/tmp/test-downloads",
    "MEGAQUEUE_NTFY_TOPIC": "test-topic",
    "MEGAQUEUE_DATABASE_URL": "sqlite:///:memory:",
    "MEGAQUEUE_MEGABASTERD_API_URL": "http://localhost:9999",
    "MEGAQUEUE_MEGABASTERD_GRACE_PERIOD": "30",
})

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from megaqueue.models import Base, Download, DownloadFile
from megaqueue import models
from megaqueue import app as app_module
from megaqueue import sync as sync_module
from megaqueue import lifecycle as lifecycle_module


@pytest.fixture()
def db_session():
    """Create an in-memory SQLite database with a fresh session for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = scoped_session(session_factory)

    # Patch db_session in every module that imports it directly
    originals = {
        "models": models.db_session,
        "app": app_module.db_session,
        "sync": sync_module.db_session,
        "lifecycle": lifecycle_module.db_session,
    }
    models.db_session = session
    app_module.db_session = session
    sync_module.db_session = session
    lifecycle_module.db_session = session

    yield session

    session.remove()
    models.db_session = originals["models"]
    app_module.db_session = originals["app"]
    sync_module.db_session = originals["sync"]
    lifecycle_module.db_session = originals["lifecycle"]
    engine.dispose()


@pytest.fixture()
def app(db_session):
    """Create a Flask test app with CSRF disabled and test database."""
    from megaqueue.app import app as flask_app

    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False

    yield flask_app


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def sample_download(db_session):
    """Create a sample download with two files."""
    from megaqueue.enums import DownloadStatus, MediaType
    dl = Download(title="Test Movie", year=2024, media_type=MediaType.MOVIE, status=DownloadStatus.QUEUED)
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc123#key1"))
    dl.files.append(DownloadFile(url="https://mega.nz/file/def456#key2"))
    db_session.add(dl)
    db_session.commit()
    return dl
