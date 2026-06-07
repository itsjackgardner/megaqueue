from unittest.mock import patch

import pytest

from megaqueue.enums import DownloadStatus, FileStatus, MetadataConfidence
from megaqueue.lifecycle import derive_download_status, resolve_source_paths
from megaqueue.models import Download, DownloadFile


def test_derive_all_finished_high_confidence(db_session):
    dl = Download(title="Test", media_type="movie", status=DownloadStatus.DOWNLOADING,
                  metadata_confidence=MetadataConfidence.HIGH)
    dl.files.append(DownloadFile(url="u1", status=FileStatus.FINISHED))
    dl.files.append(DownloadFile(url="u2", status=FileStatus.FINISHED))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.PROCESSING


def test_derive_all_finished_low_confidence(db_session):
    """All files finished but metadata confidence is low -> NEEDS_REVIEW, not PROCESSING."""
    dl = Download(title="Test", media_type="movie", status=DownloadStatus.DOWNLOADING,
                  metadata_confidence=MetadataConfidence.LOW)
    dl.files.append(DownloadFile(url="u1", status=FileStatus.FINISHED))
    dl.files.append(DownloadFile(url="u2", status=FileStatus.FINISHED))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.NEEDS_REVIEW


def test_derive_all_failed(db_session):
    dl = Download(title="Test", media_type="movie", status=DownloadStatus.DOWNLOADING)
    dl.files.append(DownloadFile(url="u1", status=FileStatus.FAILED))
    dl.files.append(DownloadFile(url="u2", status=FileStatus.FAILED))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.FAILED


def test_derive_mixed_downloading(db_session):
    dl = Download(title="Test", media_type="movie", status=DownloadStatus.QUEUED)
    dl.files.append(DownloadFile(url="u1", status=FileStatus.DOWNLOADING))
    dl.files.append(DownloadFile(url="u2", status=FileStatus.QUEUED))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.DOWNLOADING


def test_derive_some_finished_some_downloading(db_session):
    dl = Download(title="Test", media_type="movie", status=DownloadStatus.DOWNLOADING)
    dl.files.append(DownloadFile(url="u1", status=FileStatus.FINISHED))
    dl.files.append(DownloadFile(url="u2", status=FileStatus.DOWNLOADING))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.DOWNLOADING


def test_derive_all_queued(db_session):
    dl = Download(title="Test", media_type="movie", status=DownloadStatus.QUEUED)
    dl.files.append(DownloadFile(url="u1", status=FileStatus.QUEUED))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.QUEUED


def test_derive_empty_files(db_session):
    dl = Download(title="Test", media_type="movie", status=DownloadStatus.QUEUED)
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.QUEUED


# --- Resolve Source Paths ---

def test_resolve_source_paths_from_leaf_names(db_session, tmp_path):
    dl = Download(title="Movie", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key", name="movie.mkv", status=FileStatus.FINISHED)
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.lifecycle.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        paths = resolve_source_paths(dl)

    assert len(paths) == 1
    assert paths[0] == tmp_path / "movie.mkv"


def test_resolve_source_paths_uses_children_for_folder(db_session, tmp_path):
    dl = Download(title="Show", media_type="tv")
    folder_df = DownloadFile(url="https://mega.nz/folder/abc#key", status=FileStatus.QUEUED)
    dl.files.append(folder_df)
    db_session.add(dl)
    db_session.commit()

    for i in range(1, 3):
        child = DownloadFile(
            download_id=dl.id, parent_id=folder_df.id,
            url=f"https://mega.nz/#N!id{i}!k{i}###n=abc",
            name=f"ep0{i}.mkv", status=FileStatus.FINISHED,
        )
        db_session.add(child)
    db_session.commit()
    db_session.refresh(dl)

    with patch("megaqueue.lifecycle.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        paths = resolve_source_paths(dl)

    assert len(paths) == 2
    assert tmp_path / "ep01.mkv" in paths
    assert tmp_path / "ep02.mkv" in paths


def test_resolve_source_paths_raises_when_name_missing(db_session, tmp_path):
    dl = Download(title="Movie", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key", name=None, status=FileStatus.FINISHED)
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.lifecycle.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        with pytest.raises(ValueError, match="name not set"):
            resolve_source_paths(dl)
