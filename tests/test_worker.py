from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from megaqueue.models import Download, DownloadFile
from megaqueue.worker import (
    _normalize_mega_url,
    _extract_folder_id,
    _match_megabasterd_files,
    _maybe_expand_folder_files,
    _derive_download_status,
    _update_file_from_megabasterd,
    _resolve_source_paths,
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


# --- Folder ID Extraction ---

def test_extract_folder_id_from_folder_url():
    url = "https://mega.nz/folder/LAlWVZbQ#HUccRplmJSvCF-9bOuyFJg"
    assert _extract_folder_id(url) == "LAlWVZbQ"


def test_extract_folder_id_from_per_file_url():
    url = "https://mega.nz/#N!HIkkFLQZ!9lZBceIU9TmzfU4QrMoPbjVsQsLACzxMHt_wy7CI4bg###n=LAlWVZbQ"
    assert _extract_folder_id(url) == "LAlWVZbQ"


def test_extract_folder_id_plain_file_url_returns_none():
    url = "https://mega.nz/file/abc123#key456"
    assert _extract_folder_id(url) is None


def test_extract_folder_id_empty_string_returns_none():
    assert _extract_folder_id("") is None


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


def test_match_folder_url_via_folder_id(db_session):
    """Folder-split entries match via ###n={folderId} suffix (Tier 3)."""
    folder_url = "https://mega.nz/folder/LAlWVZbQ#HUccRplmJSvCF-9bOuyFJg"
    dl = Download(title="Industry S01", media_type="tv")
    df = DownloadFile(url=folder_url)
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [
        {"url": f"https://mega.nz/#N!id{i}!key{i}###n=LAlWVZbQ", "name": f"S01E0{i}.mkv",
         "bytesLoaded": 0, "bytesTotal": 1000, "speed": 0, "finished": False, "status": "Downloading"}
        for i in range(1, 9)
    ]
    matched = _match_megabasterd_files(mb_downloads, dl.files)

    assert df.id in matched
    assert len(matched[df.id]) == 8


def test_match_tier1_unaffected_by_tier3(db_session):
    """Tier 1 direct URL match still works when Tier 3 logic is present."""
    dl = Download(title="Movie", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc123#key1")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [{"url": "https://mega.nz/file/abc123#key1", "name": "movie.mkv",
                     "bytesLoaded": 500, "bytesTotal": 1000, "speed": 100,
                     "finished": False, "status": "Downloading"}]
    matched = _match_megabasterd_files(mb_downloads, dl.files)

    assert df.id in matched
    assert len(matched[df.id]) == 1


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

@patch("megaqueue.worker.notify_failure")
@patch("megaqueue.worker.notify_completion")
@patch("megaqueue.worker.filebot_organizer")
def test_sync_transitions_to_downloading(mock_fb, mock_notify_ok, mock_notify_fail, db_session):
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


@patch("megaqueue.worker.notify_failure")
@patch("megaqueue.worker.notify_completion")
@patch("megaqueue.worker.filebot_organizer")
def test_sync_triggers_post_processing(mock_fb, mock_notify_ok, mock_notify_fail, db_session):
    mock_fb.organize_download.return_value = ["/dest/movie.mkv"]

    dl = Download(title="Test", media_type="movie", status="downloading")
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key", status="queued"))
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [
        {"url": "https://mega.nz/file/abc#key", "name": "movie.mkv",
         "bytesLoaded": 1000, "bytesTotal": 1000, "speed": 0,
         "finished": True, "status": "OK"}
    ]

    client = MagicMock()
    _sync_active_downloads(client, mb_downloads)

    db_session.refresh(dl)
    assert dl.status == "complete"
    mock_fb.organize_download.assert_called_once()
    mock_notify_ok.assert_called_once()


# --- Folder Expansion ---

def test_expand_folder_files_creates_children(db_session):
    """First tick with folder split creates child DownloadFile records."""
    folder_url = "https://mega.nz/folder/abc123#key"
    dl = Download(title="Show", media_type="tv")
    df = DownloadFile(url=folder_url)
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_entries = [
        {"url": f"https://mega.nz/#N!id{i}!key{i}###n=abc123", "name": f"ep0{i}.mkv"}
        for i in range(1, 4)
    ]
    initial_matches = {df.id: mb_entries}

    _maybe_expand_folder_files(dl, initial_matches)
    db_session.flush()
    db_session.refresh(dl)

    assert len(df.children) == 3
    child_names = {c.name for c in df.children}
    assert "ep01.mkv" in child_names
    assert "ep02.mkv" in child_names
    assert "ep03.mkv" in child_names


def test_expand_folder_files_idempotent(db_session):
    """Second tick with existing children does not create duplicates."""
    folder_url = "https://mega.nz/folder/abc123#key"
    dl = Download(title="Show", media_type="tv")
    df = DownloadFile(url=folder_url)
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    # Create children manually (simulating prior expansion)
    child = DownloadFile(
        download_id=dl.id, parent_id=df.id,
        url="https://mega.nz/#N!id1!key1###n=abc123", name="ep01.mkv", status="queued",
    )
    db_session.add(child)
    db_session.commit()
    db_session.refresh(df)

    mb_entries = [
        {"url": "https://mega.nz/#N!id1!key1###n=abc123", "name": "ep01.mkv"},
        {"url": "https://mega.nz/#N!id2!key2###n=abc123", "name": "ep02.mkv"},
    ]
    initial_matches = {df.id: mb_entries}

    _maybe_expand_folder_files(dl, initial_matches)
    db_session.flush()
    db_session.refresh(df)

    # Still only 1 child (idempotent)
    assert len(df.children) == 1


def test_expand_does_not_expand_non_folder_urls(db_session):
    """Non-folder URLs are not expanded even if matched by multiple entries."""
    dl = Download(title="Movie", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    initial_matches = {df.id: [
        {"url": "https://mega.nz/file/abc#key", "name": "movie.mkv"},
    ]}

    _maybe_expand_folder_files(dl, initial_matches)
    db_session.flush()
    db_session.refresh(df)

    assert len(df.children) == 0


# --- Resolve Source Paths ---

def test_resolve_source_paths_from_leaf_names(db_session, tmp_path):
    """Source paths are resolved from DownloadFile.name for leaf files."""
    dl = Download(title="Movie", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key", name="movie.mkv", status="finished")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.worker.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        paths = _resolve_source_paths(dl)

    assert len(paths) == 1
    assert paths[0] == tmp_path / "movie.mkv"


def test_resolve_source_paths_uses_children_for_folder(db_session, tmp_path):
    """For expanded folder downloads, paths come from children not the parent."""
    dl = Download(title="Show", media_type="tv")
    folder_df = DownloadFile(url="https://mega.nz/folder/abc#key", status="queued")
    dl.files.append(folder_df)
    db_session.add(dl)
    db_session.commit()

    # Add children
    for i in range(1, 3):
        child = DownloadFile(
            download_id=dl.id, parent_id=folder_df.id,
            url=f"https://mega.nz/#N!id{i}!k{i}###n=abc",
            name=f"ep0{i}.mkv", status="finished",
        )
        db_session.add(child)
    db_session.commit()
    db_session.refresh(dl)

    with patch("megaqueue.worker.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        paths = _resolve_source_paths(dl)

    assert len(paths) == 2
    assert tmp_path / "ep01.mkv" in paths
    assert tmp_path / "ep02.mkv" in paths


def test_resolve_source_paths_raises_when_name_missing(db_session, tmp_path):
    """Raises ValueError when a leaf file has no name set."""
    dl = Download(title="Movie", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key", name=None, status="finished")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.worker.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        with pytest.raises(ValueError, match="name not set"):
            _resolve_source_paths(dl)


# --- Integrity Sweep ---

@patch("megaqueue.worker.notify_failure")
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


@patch("megaqueue.worker.notify_failure")
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
