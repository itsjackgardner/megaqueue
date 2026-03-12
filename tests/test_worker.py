from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from models import Download, DownloadFile
from worker import (
    _normalize_mega_url,
    _match_megabasterd_files,
    _derive_download_status,
    _update_file_from_megabasterd,
    _sync_active_downloads,
    _integrity_sweep,
)


# --- URL Normalization ---

def test_normalize_old_format():
    url = "https://mega.nz/#!abcdef!key123"
    assert _normalize_mega_url(url) == "abcdef#key123"


def test_normalize_new_format():
    url = "https://mega.nz/file/abcdef#key123"
    assert _normalize_mega_url(url) == "abcdef#key123"


def test_normalize_old_and_new_match():
    old = "https://mega.nz/#!abcdef!key123"
    new = "https://mega.nz/file/abcdef#key123"
    assert _normalize_mega_url(old) == _normalize_mega_url(new)


def test_normalize_folder_file_format():
    url = "https://mega.nz/#N!abcdef!key123###n=folderid"
    # Should strip the folder suffix and normalize
    result = _normalize_mega_url(url)
    assert "folderid" not in result
    assert "abcdef" in result


def test_normalize_passthrough_unknown():
    url = "https://example.com/unknown"
    assert _normalize_mega_url(url) == url


# --- File Matching ---

def test_match_direct_url(db_session):
    dl = Download(title="Test", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc123#key1")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [{"url": "https://mega.nz/file/abc123#key1", "name": "file.mkv"}]
    matched = _match_megabasterd_files(mb_downloads, dl.files)

    assert df.id in matched
    assert len(matched[df.id]) == 1


def test_match_old_to_new_format(db_session):
    dl = Download(title="Test", media_type="movie")
    df = DownloadFile(url="https://mega.nz/#!abc123!key1")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [{"url": "https://mega.nz/file/abc123#key1", "name": "file.mkv"}]
    matched = _match_megabasterd_files(mb_downloads, dl.files)

    assert df.id in matched


def test_match_by_source_url(db_session):
    """Folder-split entries match via sourceUrl."""
    dl = Download(title="Test", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/folder1#folderkey")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [
        {"url": "https://mega.nz/file/split1#k1", "sourceUrl": "https://mega.nz/file/folder1#folderkey", "name": "part1"},
        {"url": "https://mega.nz/file/split2#k2", "sourceUrl": "https://mega.nz/file/folder1#folderkey", "name": "part2"},
    ]
    matched = _match_megabasterd_files(mb_downloads, dl.files)

    assert df.id in matched
    assert len(matched[df.id]) == 2


def test_match_no_match(db_session):
    dl = Download(title="Test", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [{"url": "https://mega.nz/file/xyz#other", "name": "unrelated"}]
    matched = _match_megabasterd_files(mb_downloads, dl.files)

    assert df.id not in matched


# --- Status Derivation ---

def test_derive_all_finished(db_session):
    dl = Download(title="Test", media_type="movie", status="downloading")
    dl.files.append(DownloadFile(url="u1", status="finished"))
    dl.files.append(DownloadFile(url="u2", status="finished"))
    db_session.add(dl)
    db_session.commit()

    assert _derive_download_status(dl) == "processing"


def test_derive_all_failed(db_session):
    dl = Download(title="Test", media_type="movie", status="downloading")
    dl.files.append(DownloadFile(url="u1", status="failed"))
    dl.files.append(DownloadFile(url="u2", status="failed"))
    db_session.add(dl)
    db_session.commit()

    assert _derive_download_status(dl) == "failed"


def test_derive_mixed_downloading(db_session):
    dl = Download(title="Test", media_type="movie", status="queued")
    dl.files.append(DownloadFile(url="u1", status="downloading"))
    dl.files.append(DownloadFile(url="u2", status="queued"))
    db_session.add(dl)
    db_session.commit()

    assert _derive_download_status(dl) == "downloading"


def test_derive_some_finished_some_downloading(db_session):
    dl = Download(title="Test", media_type="movie", status="downloading")
    dl.files.append(DownloadFile(url="u1", status="finished"))
    dl.files.append(DownloadFile(url="u2", status="downloading"))
    db_session.add(dl)
    db_session.commit()

    assert _derive_download_status(dl) == "downloading"


def test_derive_all_queued(db_session):
    dl = Download(title="Test", media_type="movie", status="queued")
    dl.files.append(DownloadFile(url="u1", status="queued"))
    db_session.add(dl)
    db_session.commit()

    assert _derive_download_status(dl) == "queued"


def test_derive_empty_files(db_session):
    dl = Download(title="Test", media_type="movie", status="queued")
    db_session.add(dl)
    db_session.commit()

    assert _derive_download_status(dl) == "queued"


# --- Update File From Megabasterd ---

def test_update_file_progress(db_session):
    df = DownloadFile(url="u1", status="queued")
    dl = Download(title="Test", media_type="movie")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    _update_file_from_megabasterd(df, [
        {"bytesLoaded": 500, "bytesTotal": 1000, "speed": 100, "finished": False, "status": "Downloading"}
    ])

    assert df.progress_bytes == 500
    assert df.total_bytes == 1000
    assert df.speed == 100
    assert df.status == "downloading"


def test_update_file_finished(db_session):
    df = DownloadFile(url="u1", status="downloading")
    dl = Download(title="Test", media_type="movie")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    _update_file_from_megabasterd(df, [
        {"bytesLoaded": 1000, "bytesTotal": 1000, "speed": 0, "finished": True, "status": "OK", "name": "movie.mkv"}
    ])

    assert df.status == "finished"
    assert df.speed == 0
    assert df.name == "movie.mkv"


def test_update_file_error(db_session):
    df = DownloadFile(url="u1", status="downloading")
    dl = Download(title="Test", media_type="movie")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    _update_file_from_megabasterd(df, [
        {"bytesLoaded": 100, "bytesTotal": 1000, "speed": 0, "finished": False, "status": "Error", "error": "Checksum failed"}
    ])

    assert df.status == "failed"
    assert df.error_message == "Checksum failed"


def test_update_file_509_bandwidth(db_session):
    df = DownloadFile(url="u1", status="downloading")
    dl = Download(title="Test", media_type="movie")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    _update_file_from_megabasterd(df, [
        {"bytesLoaded": 100, "bytesTotal": 1000, "speed": 0, "finished": False,
         "status": "509 Bandwidth Limit Exceeded", "error509Count": 3}
    ])

    assert "509" in df.error_message
    assert "3 workers" in df.error_message


def test_update_multi_entry_aggregation(db_session):
    """Folder-split: multiple entries aggregated into one file."""
    df = DownloadFile(url="u1", status="queued")
    dl = Download(title="Test", media_type="movie")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    _update_file_from_megabasterd(df, [
        {"bytesLoaded": 200, "bytesTotal": 500, "speed": 50, "finished": False, "status": "Downloading"},
        {"bytesLoaded": 300, "bytesTotal": 500, "speed": 75, "finished": False, "status": "Downloading"},
    ])

    assert df.progress_bytes == 500
    assert df.total_bytes == 1000
    assert df.speed == 125


# --- Sync Active Downloads (integration-style) ---

@patch("worker.notify_failure")
@patch("worker.notify_completion")
@patch("worker.organize_download")
def test_sync_transitions_to_downloading(mock_organize, mock_notify_ok, mock_notify_fail, db_session):
    dl = Download(title="Test", media_type="movie", status="queued")
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key"))
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [
        {"url": "https://mega.nz/file/abc#key", "name": "movie.mkv",
         "bytesLoaded": 100, "bytesTotal": 1000, "speed": 50,
         "finished": False, "status": "Downloading"}
    ]

    client = MagicMock()
    _sync_active_downloads(client, mb_downloads)

    db_session.refresh(dl)
    assert dl.status == "downloading"


@patch("worker.notify_failure")
@patch("worker.notify_completion")
@patch("worker.organize_download", return_value=["/dest/movie.mkv"])
def test_sync_triggers_post_processing(mock_organize, mock_notify_ok, mock_notify_fail, db_session):
    dl = Download(title="Test", media_type="movie", status="downloading")
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key", status="queued"))
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [
        {"url": "https://mega.nz/file/abc#key", "name": "movie.mkv",
         "bytesLoaded": 1000, "bytesTotal": 1000, "speed": 0,
         "finished": True, "status": "OK", "path": "movie.mkv"}
    ]

    client = MagicMock()
    _sync_active_downloads(client, mb_downloads)

    db_session.refresh(dl)
    assert dl.status == "complete"
    mock_organize.assert_called_once()
    mock_notify_ok.assert_called_once()


# --- Integrity Sweep ---

@patch("worker.notify_failure")
def test_integrity_sweep_fails_after_grace_period(mock_notify, db_session):
    dl = Download(
        title="Test", media_type="movie", status="downloading",
        downloading_since=datetime.utcnow() - timedelta(seconds=60),
    )
    dl.files.append(DownloadFile(url="u1", status="downloading"))
    db_session.add(dl)
    db_session.commit()

    # No matched file IDs — file is missing from megabasterd
    _integrity_sweep(matched_file_ids=set())

    db_session.refresh(dl)
    assert dl.files[0].status == "failed"
    assert "Disappeared" in dl.files[0].error_message


@patch("worker.notify_failure")
def test_integrity_sweep_respects_grace_period(mock_notify, db_session):
    dl = Download(
        title="Test", media_type="movie", status="downloading",
        downloading_since=datetime.utcnow() - timedelta(seconds=5),  # within grace period
    )
    dl.files.append(DownloadFile(url="u1", status="downloading"))
    db_session.add(dl)
    db_session.commit()

    _integrity_sweep(matched_file_ids=set())

    db_session.refresh(dl)
    assert dl.files[0].status == "downloading"  # not failed yet
