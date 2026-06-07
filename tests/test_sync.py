from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from megaqueue.enums import DownloadStatus, FileStatus, MetadataConfidence
from megaqueue.models import Download, DownloadFile
from megaqueue.sync import (
    match_megabasterd_files,
    maybe_expand_folder_files,
    update_file_from_megabasterd,
    submit_pending,
    sync_active,
    integrity_sweep,
)


# --- File Matching ---

def test_match_direct_url(db_session):
    dl = Download(title="Test", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc123#key1")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [{"url": "https://mega.nz/file/abc123#key1", "name": "file.mkv"}]
    matched = match_megabasterd_files(mb_downloads, dl.files)

    assert df.id in matched
    assert len(matched[df.id]) == 1


def test_match_old_to_new_format(db_session):
    dl = Download(title="Test", media_type="movie")
    df = DownloadFile(url="https://mega.nz/#!abc123!key1")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [{"url": "https://mega.nz/file/abc123#key1", "name": "file.mkv"}]
    matched = match_megabasterd_files(mb_downloads, dl.files)

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
    matched = match_megabasterd_files(mb_downloads, dl.files)

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
    matched = match_megabasterd_files(mb_downloads, dl.files)

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
    matched = match_megabasterd_files(mb_downloads, dl.files)

    assert df.id in matched
    assert len(matched[df.id]) == 1


def test_match_no_match(db_session):
    dl = Download(title="Test", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [{"url": "https://mega.nz/file/xyz#other", "name": "unrelated"}]
    matched = match_megabasterd_files(mb_downloads, dl.files)

    assert df.id not in matched


# --- sourceUrl Matching ---

def test_match_by_source_url_folder(db_session):
    """Folder-split entries match via sourceUrl to a folder DownloadFile."""
    folder_url = "https://mega.nz/folder/LAlWVZbQ#HUccRplmJSvCF-9bOuyFJg"
    dl = Download(title="Show", media_type="tv")
    df = DownloadFile(url=folder_url)
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [
        {"url": f"https://mega.nz/#N!id{i}!key{i}###n=LAlWVZbQ",
         "sourceUrl": folder_url, "name": f"ep0{i}.mkv"}
        for i in range(1, 4)
    ]
    matched = match_megabasterd_files(mb_downloads, dl.files)

    assert df.id in matched
    assert len(matched[df.id]) == 3


# --- Update File From Megabasterd ---

def test_update_file_progress(db_session):
    df = DownloadFile(url="u1", status=FileStatus.QUEUED)
    dl = Download(title="Test", media_type="movie")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    update_file_from_megabasterd(df, [
        {"bytesLoaded": 500, "bytesTotal": 1000, "speed": 100, "finished": False, "status": "Downloading"}
    ])

    assert df.progress_bytes == 500
    assert df.total_bytes == 1000
    assert df.speed == 100
    assert df.status == FileStatus.DOWNLOADING


def test_update_file_finished(db_session):
    df = DownloadFile(url="u1", status=FileStatus.DOWNLOADING)
    dl = Download(title="Test", media_type="movie")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    update_file_from_megabasterd(df, [
        {"bytesLoaded": 1000, "bytesTotal": 1000, "speed": 0, "finished": True, "status": "OK", "name": "movie.mkv"}
    ])

    assert df.status == FileStatus.FINISHED
    assert df.speed == 0
    assert df.name == "movie.mkv"


def test_update_file_error(db_session):
    df = DownloadFile(url="u1", status=FileStatus.DOWNLOADING)
    dl = Download(title="Test", media_type="movie")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    update_file_from_megabasterd(df, [
        {"bytesLoaded": 100, "bytesTotal": 1000, "speed": 0, "finished": False, "status": "Error", "error": "Checksum failed"}
    ])

    assert df.status == FileStatus.FAILED
    assert df.error_message == "Checksum failed"


def test_update_file_509_bandwidth(db_session):
    df = DownloadFile(url="u1", status=FileStatus.DOWNLOADING)
    dl = Download(title="Test", media_type="movie")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    update_file_from_megabasterd(df, [
        {"bytesLoaded": 100, "bytesTotal": 1000, "speed": 0, "finished": False,
         "status": "509 Bandwidth Limit Exceeded", "error509Count": 3}
    ])

    assert "509" in df.error_message
    assert "3 workers" in df.error_message


def test_update_multi_entry_aggregation(db_session):
    """Folder-split: multiple entries aggregated into one file."""
    df = DownloadFile(url="u1", status=FileStatus.QUEUED)
    dl = Download(title="Test", media_type="movie")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    update_file_from_megabasterd(df, [
        {"bytesLoaded": 200, "bytesTotal": 500, "speed": 50, "finished": False, "status": "Downloading"},
        {"bytesLoaded": 300, "bytesTotal": 500, "speed": 75, "finished": False, "status": "Downloading"},
    ])

    assert df.progress_bytes == 500
    assert df.total_bytes == 1000
    assert df.speed == 125


# --- Sync Active Downloads (integration-style) ---

@patch("megaqueue.lifecycle.notify_failure")
@patch("megaqueue.lifecycle.notify_completion")
@patch("megaqueue.lifecycle.filebot_organizer")
def test_sync_transitions_to_downloading(mock_fb, mock_notify_ok, mock_notify_fail, db_session):
    dl = Download(title="Test", media_type="movie", status=DownloadStatus.QUEUED)
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key"))
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [
        {"url": "https://mega.nz/file/abc#key", "name": "movie.mkv",
         "bytesLoaded": 100, "bytesTotal": 1000, "speed": 50,
         "finished": False, "status": "Downloading"}
    ]

    client = MagicMock()
    sync_active(client, mb_downloads)

    db_session.refresh(dl)
    assert dl.status == DownloadStatus.DOWNLOADING


@patch("megaqueue.lifecycle.notify_failure")
@patch("megaqueue.lifecycle.notify_completion")
@patch("megaqueue.lifecycle.filebot_organizer")
def test_sync_triggers_post_processing(mock_fb, mock_notify_ok, mock_notify_fail, db_session):
    """A finished download with high metadata confidence runs the organiser."""
    mock_fb.organize_download.return_value = ["/dest/movie.mkv"]

    # Pre-set high confidence so derive_download_status returns PROCESSING.
    # In real flow, metadata.refresh would compute this from the filename.
    dl = Download(title="Test", media_type="movie", status=DownloadStatus.DOWNLOADING,
                  metadata_confidence=MetadataConfidence.HIGH)
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key", status=FileStatus.QUEUED))
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [
        {"url": "https://mega.nz/file/abc#key", "name": "Inception.2010.1080p.BluRay.x264.mkv",
         "bytesLoaded": 1000, "bytesTotal": 1000, "speed": 0,
         "finished": True, "status": "OK"}
    ]

    client = MagicMock()
    sync_active(client, mb_downloads)

    db_session.refresh(dl)
    assert dl.status == DownloadStatus.COMPLETE
    mock_fb.organize_download.assert_called_once()
    mock_notify_ok.assert_called_once()


@patch("megaqueue.sync.notify_needs_review")
@patch("megaqueue.lifecycle.notify_failure")
@patch("megaqueue.lifecycle.notify_completion")
@patch("megaqueue.lifecycle.filebot_organizer")
def test_sync_routes_low_confidence_to_needs_review(mock_fb, mock_ok, mock_fail, mock_review, db_session):
    """A finished download with low confidence enters NEEDS_REVIEW and notifies; organiser does not run."""
    dl = Download(media_type=None, status=DownloadStatus.DOWNLOADING,
                  metadata_confidence=MetadataConfidence.LOW)
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key", status=FileStatus.QUEUED))
    db_session.add(dl)
    db_session.commit()

    # An ambiguous filename — guessit will give a weak result.
    mb_downloads = [
        {"url": "https://mega.nz/file/abc#key", "name": "Trailer.mkv",
         "bytesLoaded": 1000, "bytesTotal": 1000, "speed": 0,
         "finished": True, "status": "OK"}
    ]

    client = MagicMock()
    sync_active(client, mb_downloads)

    db_session.refresh(dl)
    assert dl.status == DownloadStatus.NEEDS_REVIEW
    mock_fb.organize_download.assert_not_called()
    mock_review.assert_called_once()


def test_sync_skips_downloads_already_in_needs_review(db_session):
    """sync_active does not re-process NEEDS_REVIEW downloads on subsequent ticks."""
    dl = Download(title="Movie", media_type="movie", status=DownloadStatus.NEEDS_REVIEW,
                  metadata_confidence=MetadataConfidence.LOW)
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key", status=FileStatus.FINISHED,
                                 name="Movie.mkv"))
    db_session.add(dl)
    db_session.commit()

    # Status query filters to QUEUED/DOWNLOADING, so this Download is excluded.
    # Even if it slipped through, the NEEDS_REVIEW check inside the loop
    # short-circuits before any work.
    client = MagicMock()
    result = sync_active(client, [])
    assert result == set()
    db_session.refresh(dl)
    assert dl.status == DownloadStatus.NEEDS_REVIEW


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

    maybe_expand_folder_files(dl, initial_matches)
    db_session.flush()
    db_session.refresh(dl)

    assert len(df.children) == 3
    child_names = {c.name for c in df.children}
    assert "ep01.mkv" in child_names
    assert "ep02.mkv" in child_names
    assert "ep03.mkv" in child_names


def test_expand_folder_files_creates_children_old_format(db_session):
    """Old-format folder URL (mega.nz/#F!...) is expanded into child records."""
    folder_url = "https://mega.nz/#F!abc123!folderkey"
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

    maybe_expand_folder_files(dl, initial_matches)
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

    child = DownloadFile(
        download_id=dl.id, parent_id=df.id,
        url="https://mega.nz/#N!id1!key1###n=abc123", name="ep01.mkv", status=FileStatus.QUEUED,
    )
    db_session.add(child)
    db_session.commit()
    db_session.refresh(df)

    mb_entries = [
        {"url": "https://mega.nz/#N!id1!key1###n=abc123", "name": "ep01.mkv"},
        {"url": "https://mega.nz/#N!id2!key2###n=abc123", "name": "ep02.mkv"},
    ]
    initial_matches = {df.id: mb_entries}

    maybe_expand_folder_files(dl, initial_matches)
    db_session.flush()
    db_session.refresh(df)

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

    maybe_expand_folder_files(dl, initial_matches)
    db_session.flush()
    db_session.refresh(df)

    assert len(df.children) == 0


# --- Integrity Sweep ---

@patch("megaqueue.sync.notify_failure")
def test_integrity_sweep_fails_after_grace_period(mock_notify, db_session):
    dl = Download(
        title="Test", media_type="movie", status=DownloadStatus.DOWNLOADING,
        downloading_since=datetime.utcnow() - timedelta(seconds=60),
    )
    dl.files.append(DownloadFile(url="u1", status=FileStatus.DOWNLOADING))
    db_session.add(dl)
    db_session.commit()

    integrity_sweep(matched_file_ids=set())

    db_session.refresh(dl)
    assert dl.files[0].status == FileStatus.FAILED
    assert "Disappeared" in dl.files[0].error_message


@patch("megaqueue.sync.notify_failure")
def test_integrity_sweep_respects_grace_period(mock_notify, db_session):
    dl = Download(
        title="Test", media_type="movie", status=DownloadStatus.DOWNLOADING,
        downloading_since=datetime.utcnow() - timedelta(seconds=5),
    )
    dl.files.append(DownloadFile(url="u1", status=FileStatus.DOWNLOADING))
    db_session.add(dl)
    db_session.commit()

    integrity_sweep(matched_file_ids=set())

    db_session.refresh(dl)
    assert dl.files[0].status == FileStatus.DOWNLOADING


@patch("megaqueue.sync.notify_failure")
def test_integrity_sweep_skips_unsubmitted(mock_notify, db_session):
    """Downloads with downloading_since=None are excluded from integrity sweep."""
    dl = Download(
        title="Test", media_type="movie", status=DownloadStatus.QUEUED,
        downloading_since=None,
    )
    dl.files.append(DownloadFile(url="u1", status=FileStatus.QUEUED))
    db_session.add(dl)
    db_session.commit()

    integrity_sweep(matched_file_ids=set())

    db_session.refresh(dl)
    assert dl.files[0].status == FileStatus.QUEUED
    mock_notify.assert_not_called()


# --- Submit Pending Downloads ---

def test_submit_pending_stamps_downloading_since(db_session):
    dl = Download(title="Test Movie", media_type="movie", status=DownloadStatus.QUEUED)
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key"))
    db_session.add(dl)
    db_session.commit()

    assert dl.downloading_since is None

    client = MagicMock()
    submit_pending(client)

    db_session.refresh(dl)
    client.start.assert_called_once()
    assert dl.downloading_since is not None
    assert dl.status == DownloadStatus.QUEUED


def test_submit_pending_failure_marks_failed(db_session):
    dl = Download(title="Test Movie", media_type="movie", status=DownloadStatus.QUEUED)
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key"))
    db_session.add(dl)
    db_session.commit()

    client = MagicMock()
    client.start.side_effect = ConnectionError("Connection refused")
    submit_pending(client)

    db_session.refresh(dl)
    assert dl.status == DownloadStatus.FAILED
    assert "Connection refused" in dl.error_message


def test_submit_pending_skips_already_submitted(db_session):
    dl = Download(
        title="Test", media_type="movie", status=DownloadStatus.QUEUED,
        downloading_since=datetime.utcnow(),
    )
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key"))
    db_session.add(dl)
    db_session.commit()

    client = MagicMock()
    submit_pending(client)

    client.start.assert_not_called()


# --- Pending Entry Matching ---

def test_pending_entry_matches_and_prevents_sweep(db_session):
    dl = Download(
        title="Test", media_type="movie", status=DownloadStatus.QUEUED,
        downloading_since=datetime.utcnow() - timedelta(seconds=60),
    )
    df = DownloadFile(url="https://mega.nz/file/abc#key")
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [{
        "url": "https://mega.nz/file/abc#key",
        "status": "Pending",
        "finished": False,
        "bytesLoaded": 0,
        "bytesTotal": 0,
        "speed": 0,
    }]
    matched = match_megabasterd_files(mb_downloads, dl.files)

    assert df.id in matched

    integrity_sweep(matched_file_ids=set(matched.keys()))
    db_session.refresh(dl)
    assert df.status == FileStatus.QUEUED


@patch("megaqueue.lifecycle.notify_failure")
@patch("megaqueue.lifecycle.notify_completion")
@patch("megaqueue.lifecycle.filebot_organizer")
def test_pending_entry_does_not_advance_status(mock_fb, mock_ok, mock_fail, db_session):
    dl = Download(title="Test", media_type="movie", status=DownloadStatus.QUEUED,
                  downloading_since=datetime.utcnow())
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key", status=FileStatus.QUEUED))
    db_session.add(dl)
    db_session.commit()

    mb_downloads = [{
        "url": "https://mega.nz/file/abc#key",
        "status": "Pending",
        "finished": False,
        "bytesLoaded": 0,
        "bytesTotal": 0,
        "speed": 0,
    }]

    client = MagicMock()
    sync_active(client, mb_downloads)

    db_session.refresh(dl)
    assert dl.files[0].status == FileStatus.QUEUED
    assert dl.status == DownloadStatus.QUEUED
