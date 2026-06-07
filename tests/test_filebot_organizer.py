import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from megaqueue import filebot_organizer
from megaqueue.filebot_organizer import (
    _is_archive,
    _parse_final_paths,
    _fallback_scan,
    organize_download,
)


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


# --- stdout Parsing ---

def test_parse_final_paths_standard():
    stdout = "[rename] From [/dl/Movie.mkv] to [/plex/Movie (2024)/Movie.mkv]\n"
    assert _parse_final_paths(stdout) == ["/plex/Movie (2024)/Movie.mkv"]


def test_parse_final_paths_multiple():
    stdout = (
        "[rename] From [/dl/s01e01.mkv] to [/plex/Show/Season 01/Show - S01E01.mkv]\n"
        "[rename] From [/dl/s01e02.mkv] to [/plex/Show/Season 01/Show - S01E02.mkv]\n"
    )
    paths = _parse_final_paths(stdout)
    assert len(paths) == 2
    assert paths[0].endswith("S01E01.mkv")
    assert paths[1].endswith("S01E02.mkv")


def test_parse_final_paths_no_match():
    assert _parse_final_paths("Skipping... nothing to do\n") == []


# --- Fallback Scan ---

def test_fallback_scan_finds_new_files(tmp_path):
    from datetime import datetime, timedelta

    old_file = tmp_path / "old.mkv"
    old_file.write_text("old")
    import os, time
    # Set old file's mtime to 60s ago
    old_time = time.time() - 60
    os.utime(str(old_file), (old_time, old_time))

    new_file = tmp_path / "new.mkv"
    new_file.write_text("new")

    since = datetime.now() - timedelta(seconds=30)
    results = _fallback_scan(str(tmp_path), since)

    assert str(new_file) in results
    assert str(old_file) not in results


# --- organize_download ---

def _make_completed_subprocess(returncode=0, stdout="", stderr=""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


@patch("megaqueue.filebot_organizer.subprocess.run")
def test_organize_movie_no_archives(mock_run, tmp_path):
    """Non-archive movie: only rename step runs, no extract step."""
    rename_stdout = "[rename] From [/dl/Movie.mkv] to [/plex/Movie (2024)/Movie.mkv]\n"
    mock_run.return_value = _make_completed_subprocess(stdout=rename_stdout)

    dl = MagicMock(title="Movie", year=2024, media_type="movie")
    source = tmp_path / "Movie.mkv"
    source.write_text("data")

    with patch("megaqueue.filebot_organizer.config") as mock_config:
        mock_config.FILEBOT_BIN = "filebot"
        mock_config.PLEX_MOVIES_DIR = "/plex/movies"
        mock_config.PLEX_TV_DIR = "/plex/tv"
        result = organize_download(dl, [source])

    assert result == ["/plex/Movie (2024)/Movie.mkv"]
    # Only one subprocess call (rename, no extract)
    assert mock_run.call_count == 1
    args = mock_run.call_args[0][0]
    assert "-rename" in args
    assert "-extract" not in args
    # Movie downloads pass --db TheMovieDB
    db_idx = args.index("--db")
    assert args[db_idx + 1] == "TheMovieDB"


@patch("megaqueue.filebot_organizer.subprocess.run")
def test_organize_with_archives(mock_run, tmp_path):
    """Archive files: extract step runs first, then rename."""
    extract_result = _make_completed_subprocess()
    rename_stdout = "[rename] From [/tmp/x/Movie.mkv] to [/plex/Movie (2024)/Movie.mkv]\n"
    rename_result = _make_completed_subprocess(stdout=rename_stdout)
    mock_run.side_effect = [extract_result, rename_result]

    dl = MagicMock(title="Movie", year=2024, media_type="movie")
    archive = tmp_path / "movie.rar"
    archive.write_text("data")

    with patch("megaqueue.filebot_organizer.config") as mock_config:
        mock_config.FILEBOT_BIN = "filebot"
        mock_config.PLEX_MOVIES_DIR = "/plex/movies"
        mock_config.PLEX_TV_DIR = "/plex/tv"
        result = organize_download(dl, [archive])

    assert mock_run.call_count == 2
    extract_args = mock_run.call_args_list[0][0][0]
    assert "-extract" in extract_args
    rename_args = mock_run.call_args_list[1][0][0]
    assert "-rename" in rename_args


@patch("megaqueue.filebot_organizer.subprocess.run")
def test_organize_tv_uses_tv_dir(mock_run, tmp_path):
    """TV downloads use PLEX_TV_DIR."""
    rename_stdout = "[rename] From [/dl/show.mkv] to [/plex/tv/Show/Season 01/Show - S01E01.mkv]\n"
    mock_run.return_value = _make_completed_subprocess(stdout=rename_stdout)

    dl = MagicMock(title="My Show", year=None, media_type="tv")
    source = tmp_path / "show.S01E01.mkv"
    source.write_text("data")

    with patch("megaqueue.filebot_organizer.config") as mock_config:
        mock_config.FILEBOT_BIN = "filebot"
        mock_config.PLEX_MOVIES_DIR = "/plex/movies"
        mock_config.PLEX_TV_DIR = "/plex/tv"
        result = organize_download(dl, [source])

    rename_args = mock_run.call_args[0][0]
    assert "/plex/tv" in rename_args
    # TV downloads pass --db TheTVDB
    db_idx = rename_args.index("--db")
    assert rename_args[db_idx + 1] == "TheTVDB"


@patch("megaqueue.filebot_organizer.subprocess.run")
def test_organize_raises_on_nonzero_exit(mock_run, tmp_path):
    """Non-zero FileBot exit raises RuntimeError with stderr."""
    mock_run.return_value = _make_completed_subprocess(returncode=1, stderr="Error: no match found")

    dl = MagicMock(title="Movie", year=2024, media_type="movie")
    source = tmp_path / "movie.mkv"
    source.write_text("data")

    with patch("megaqueue.filebot_organizer.config") as mock_config:
        mock_config.FILEBOT_BIN = "filebot"
        mock_config.PLEX_MOVIES_DIR = "/plex/movies"
        mock_config.PLEX_TV_DIR = "/plex/tv"
        with pytest.raises(RuntimeError, match="no match found"):
            organize_download(dl, [source])


@patch("megaqueue.filebot_organizer.subprocess.run")
def test_organize_cleans_up_temp_dir_on_success(mock_run, tmp_path):
    """Temp directory is removed after successful organization."""
    rename_stdout = "[rename] From [/dl/movie.mkv] to [/plex/Movie/Movie.mkv]\n"
    mock_run.return_value = _make_completed_subprocess(stdout=rename_stdout)

    dl = MagicMock(title="Movie", year=None, media_type="movie")
    archive = tmp_path / "movie.rar"
    archive.write_text("data")

    captured_temp = []

    original_run = subprocess.run

    def capturing_run(cmd, **kwargs):
        if "-extract" in cmd:
            # Capture the temp dir from the --output arg
            out_idx = cmd.index("--output") + 1
            captured_temp.append(cmd[out_idx])
        return _make_completed_subprocess(stdout=rename_stdout)

    mock_run.side_effect = capturing_run

    with patch("megaqueue.filebot_organizer.config") as mock_config:
        mock_config.FILEBOT_BIN = "filebot"
        mock_config.PLEX_MOVIES_DIR = "/plex/movies"
        mock_config.PLEX_TV_DIR = "/plex/tv"
        organize_download(dl, [archive])

    # Temp dir should be cleaned up
    if captured_temp:
        assert not Path(captured_temp[0]).exists()


@patch("megaqueue.filebot_organizer.subprocess.run")
def test_organize_fallback_scan_when_no_stdout_paths(mock_run, tmp_path):
    """Falls back to directory scan when stdout has no parseable rename lines."""
    mock_run.return_value = _make_completed_subprocess(stdout="Skipping... already exists\n")

    dl = MagicMock(title="Movie", year=2024, media_type="movie")
    source = tmp_path / "movie.mkv"
    source.write_text("data")

    new_file = tmp_path / "plex" / "Movie.mkv"
    new_file.parent.mkdir()
    new_file.write_text("data")

    with patch("megaqueue.filebot_organizer.config") as mock_config:
        mock_config.FILEBOT_BIN = "filebot"
        mock_config.PLEX_MOVIES_DIR = str(tmp_path / "plex")
        mock_config.PLEX_TV_DIR = str(tmp_path / "plex-tv")
        with patch("megaqueue.filebot_organizer._fallback_scan", return_value=[str(new_file)]) as mock_scan:
            result = organize_download(dl, [source])

    mock_scan.assert_called_once()
    assert result == [str(new_file)]
