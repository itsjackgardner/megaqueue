from pathlib import Path
from unittest.mock import patch, MagicMock

from organizer import _is_archive, _detect_season, _collect_files, _route_movie, _route_tv, organize_download

import pytest


# --- Archive Detection ---

def test_is_archive_rar():
    assert _is_archive(Path("movie.rar")) is True


def test_is_archive_zip():
    assert _is_archive(Path("movie.zip")) is True


def test_is_archive_7z():
    assert _is_archive(Path("movie.7z")) is True


def test_is_archive_001():
    assert _is_archive(Path("movie.001")) is True


def test_is_archive_mkv():
    assert _is_archive(Path("movie.mkv")) is False


def test_is_archive_case_insensitive():
    assert _is_archive(Path("movie.RAR")) is True


# --- Season Detection ---

def test_detect_season_standard():
    assert _detect_season("breaking.bad.S02E05.mkv") == 2


def test_detect_season_lowercase():
    assert _detect_season("show.s10e01.mkv") == 10


def test_detect_season_none():
    assert _detect_season("movie.mkv") is None


# --- File Collection ---

def test_collect_files_single(tmp_path):
    f = tmp_path / "movie.mkv"
    f.write_text("data")

    files = _collect_files([f])
    assert files == [f]


def test_collect_files_directory(tmp_path):
    d = tmp_path / "folder"
    d.mkdir()
    (d / "file1.mkv").write_text("data1")
    (d / "file2.mkv").write_text("data2")

    files = _collect_files([d])
    assert len(files) == 2


def test_collect_files_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        _collect_files([tmp_path / "nonexistent"])


# --- Movie Routing ---

def test_route_movie_with_year(tmp_path):
    src = tmp_path / "inception.mkv"
    src.write_text("data")

    dl = MagicMock(title="Inception", year=2010, media_type="movie")

    with patch("organizer.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(tmp_path / "movies")
        result = _route_movie(src, dl)

    assert "Inception (2010)" in result
    assert result.endswith("inception.mkv")
    assert Path(result).exists()


def test_route_movie_without_year(tmp_path):
    src = tmp_path / "movie.mkv"
    src.write_text("data")

    dl = MagicMock(title="Untitled", year=None, media_type="movie")

    with patch("organizer.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(tmp_path / "movies")
        result = _route_movie(src, dl)

    assert "Untitled" in result
    assert "()" not in result


# --- TV Routing ---

def test_route_tv_with_season(tmp_path):
    src = tmp_path / "breaking.bad.S02E05.mkv"
    src.write_text("data")

    dl = MagicMock(title="Breaking Bad", media_type="tv")

    with patch("organizer.config") as mock_config:
        mock_config.PLEX_TV_DIR = str(tmp_path / "tv")
        result = _route_tv(src, dl)

    assert "Breaking Bad" in result
    assert "Season 02" in result
    assert Path(result).exists()


def test_route_tv_no_season(tmp_path):
    src = tmp_path / "special.mkv"
    src.write_text("data")

    dl = MagicMock(title="Some Show", media_type="tv")

    with patch("organizer.config") as mock_config:
        mock_config.PLEX_TV_DIR = str(tmp_path / "tv")
        result = _route_tv(src, dl)

    assert "Some Show" in result
    assert "Season" not in result


# --- Full Organize Download ---

def test_organize_movie_end_to_end(tmp_path):
    """Full organize flow: single movie file moved to Plex dir, source cleaned up."""
    src_file = tmp_path / "downloads" / "inception.mkv"
    src_file.parent.mkdir()
    src_file.write_text("movie data")

    movies_dir = tmp_path / "movies"
    dl = MagicMock(title="Inception", year=2010, media_type="movie", files=[])

    with patch("organizer.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(movies_dir)
        mock_config.PLEX_TV_DIR = str(tmp_path / "tv")
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path / "downloads")
        result = organize_download(dl, [src_file])

    assert len(result) == 1
    assert "Inception (2010)" in result[0]
    assert Path(result[0]).exists()
    # Source file should be cleaned up
    assert not src_file.exists()


def test_organize_tv_episode(tmp_path):
    src_file = tmp_path / "downloads" / "show.S03E07.mkv"
    src_file.parent.mkdir()
    src_file.write_text("episode data")

    tv_dir = tmp_path / "tv"
    dl = MagicMock(title="My Show", year=None, media_type="tv", files=[])

    with patch("organizer.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(tmp_path / "movies")
        mock_config.PLEX_TV_DIR = str(tv_dir)
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path / "downloads")
        result = organize_download(dl, [src_file])

    assert len(result) == 1
    assert "My Show" in result[0]
    assert "Season 03" in result[0]


def test_organize_cleanup_empty_dir(tmp_path):
    """Source directory should be removed after all files are organized."""
    src_dir = tmp_path / "downloads" / "movie_folder"
    src_dir.mkdir(parents=True)
    (src_dir / "movie.mkv").write_text("data")

    movies_dir = tmp_path / "movies"
    dl = MagicMock(title="Test", year=2024, media_type="movie", files=[])

    with patch("organizer.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(movies_dir)
        mock_config.PLEX_TV_DIR = str(tmp_path / "tv")
        mock_config.MEGABASTERD_DOWNLOAD_DIR = str(tmp_path / "downloads")
        organize_download(dl, [src_dir])

    assert not src_dir.exists()
