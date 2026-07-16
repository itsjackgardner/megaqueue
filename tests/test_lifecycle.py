from unittest.mock import patch

import pytest

from megaqueue.enums import DownloadStatus, FileStatus, MetadataConfidence, MetadataSource
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
    # Named files trigger the review gate.
    dl.files.append(DownloadFile(url="u1", name="something.mkv", status=FileStatus.FINISHED))
    dl.files.append(DownloadFile(url="u2", name="other.mkv", status=FileStatus.FINISHED))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.NEEDS_REVIEW


def test_derive_needs_review_fires_while_files_still_downloading(db_session):
    """Low confidence with at least one named file should trigger review BEFORE completion."""
    dl = Download(status=DownloadStatus.DOWNLOADING,
                  metadata_confidence=MetadataConfidence.LOW)
    dl.files.append(DownloadFile(url="u1", name="random.mkv", status=FileStatus.DOWNLOADING))
    dl.files.append(DownloadFile(url="u2", name=None, status=FileStatus.QUEUED))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.NEEDS_REVIEW


def test_derive_no_named_files_does_not_trigger_review(db_session):
    """Low confidence is the default; without filenames yet, we just stay QUEUED/DOWNLOADING."""
    dl = Download(status=DownloadStatus.QUEUED,
                  metadata_confidence=MetadataConfidence.LOW)
    dl.files.append(DownloadFile(url="u1", name=None, status=FileStatus.QUEUED))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.QUEUED


def test_derive_user_resolved_skips_review_gate(db_session):
    """metadata_source=USER means the user has resolved; the review gate is closed
    even if confidence somehow regresses to LOW."""
    dl = Download(title="X", status=DownloadStatus.DOWNLOADING,
                  metadata_confidence=MetadataConfidence.LOW,
                  metadata_source=MetadataSource.USER)
    dl.files.append(DownloadFile(url="u1", name="anything.mkv", status=FileStatus.FINISHED))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.PROCESSING


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

    (tmp_path / "movie.mkv").touch()

    with patch("megaqueue.lifecycle.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        leaves, paths, pre_extracted = resolve_source_paths(dl)

    assert len(paths) == 1
    assert paths[0] == tmp_path / "movie.mkv"
    assert pre_extracted == [False]
    assert len(leaves) == 1


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

    (tmp_path / "ep01.mkv").touch()
    (tmp_path / "ep02.mkv").touch()

    with patch("megaqueue.lifecycle.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        leaves, paths, pre_extracted = resolve_source_paths(dl)

    assert len(paths) == 2
    assert tmp_path / "ep01.mkv" in paths
    assert tmp_path / "ep02.mkv" in paths
    assert pre_extracted == [False, False]


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


# --- Pre-extracted archive fallback ---


def test_resolve_source_paths_fallback_to_pre_extracted_dir(db_session, tmp_path):
    dl = Download(title="Movie", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key", name="H2OBoy.rar", status=FileStatus.FINISHED)
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    extracted_dir = tmp_path / "H2OBoy"
    extracted_dir.mkdir()
    (extracted_dir / "The Waterboy (1998).mkv").touch()

    with patch("megaqueue.lifecycle.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        leaves, paths, pre_extracted = resolve_source_paths(dl)

    assert len(paths) == 1
    assert paths[0] == extracted_dir
    assert pre_extracted == [True]


def test_resolve_source_paths_no_fallback_for_non_archive(db_session, tmp_path):
    dl = Download(title="Movie", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key", name="movie.mkv", status=FileStatus.FINISHED)
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.lifecycle.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            resolve_source_paths(dl)


def test_resolve_source_paths_fallback_rejects_no_media_dir(db_session, tmp_path):
    dl = Download(title="Movie", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key", name="movie.rar", status=FileStatus.FINISHED)
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    extracted_dir = tmp_path / "movie"
    extracted_dir.mkdir()
    (extracted_dir / "readme.txt").touch()

    with patch("megaqueue.lifecycle.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        with pytest.raises(FileNotFoundError, match="contains no media files"):
            resolve_source_paths(dl)


def test_resolve_source_paths_fallback_no_dir_exists(db_session, tmp_path):
    dl = Download(title="Movie", media_type="movie")
    df = DownloadFile(url="https://mega.nz/file/abc#key", name="movie.rar", status=FileStatus.FINISHED)
    dl.files.append(df)
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.lifecycle.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        with pytest.raises(FileNotFoundError, match="also checked for pre-extracted"):
            resolve_source_paths(dl)


# --- Status derivation with mixed finished + queued (re-check scenario) ---

def test_derive_mixed_finished_and_queued_after_recheck(db_session):
    """After re-check adds new queued files alongside finished ones, status is DOWNLOADING."""
    dl = Download(title="Show", media_type="tv", status=DownloadStatus.DOWNLOADING,
                  metadata_confidence=MetadataConfidence.HIGH)
    dl.files.append(DownloadFile(url="u1", name="ep01.mkv", status=FileStatus.FINISHED))
    dl.files.append(DownloadFile(url="u2", name="ep02.mkv", status=FileStatus.FINISHED))
    dl.files.append(DownloadFile(url="u3", name="ep03.mkv", status=FileStatus.QUEUED))
    db_session.add(dl)
    db_session.commit()

    assert derive_download_status(dl) == DownloadStatus.DOWNLOADING


# --- resolve_source_paths skips already-organised files ---

def test_resolve_source_paths_skips_already_organised(db_session, tmp_path):
    """Files with file_path already set are skipped during resolve."""
    dl = Download(title="Show", media_type="tv")
    df1 = DownloadFile(url="u1", name="ep01.mkv", status=FileStatus.FINISHED,
                       file_path="/plex/tv/Show/Season 01/ep01.mkv")
    df2 = DownloadFile(url="u2", name="ep02.mkv", status=FileStatus.FINISHED)
    dl.files.extend([df1, df2])
    db_session.add(dl)
    db_session.commit()

    (tmp_path / "ep02.mkv").touch()

    with patch("megaqueue.lifecycle.config") as mock_config:
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path)
        leaves, paths, pre_extracted = resolve_source_paths(dl)

    assert len(leaves) == 1
    assert leaves[0].name == "ep02.mkv"
    assert len(paths) == 1
    assert paths[0] == tmp_path / "ep02.mkv"
