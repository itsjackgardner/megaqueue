import shutil
from unittest.mock import patch, MagicMock

import pytest

from megaqueue.enums import FileStatus, MediaType
from megaqueue.models import Download, DownloadFile
from megaqueue.organiser import (
    _check_unrar,
    _has_media_files,
    _is_archive,
    _move,
    _sanitize,
    _route_movie_main,
    _route_movie_extra,
    _route_tv,
    organize_download,
)


# --- Archive detection ---

def test_is_archive_rar(tmp_path):
    assert _is_archive(tmp_path / "movie.rar") is True


def test_is_archive_zip(tmp_path):
    assert _is_archive(tmp_path / "movie.zip") is True


def test_is_archive_7z(tmp_path):
    assert _is_archive(tmp_path / "movie.7z") is True


def test_is_archive_mkv(tmp_path):
    assert _is_archive(tmp_path / "movie.mkv") is False


# --- Sanitisation ---

def test_sanitize_strips_illegal_chars():
    assert _sanitize("foo:bar*baz?") == "foobarbaz"


def test_sanitize_preserves_spaces():
    assert _sanitize("My Movie") == "My Movie"


# --- Routing ---

def test_route_movie_main_with_year(tmp_path):
    dl = Download(title="Birth", year=2004, media_type=MediaType.MOVIE)
    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = "/plex/movies"
        dest = _route_movie_main(tmp_path / "Birth.2004.mkv", dl)
    assert str(dest) == "/plex/movies/Birth (2004)/Birth (2004).mkv"


def test_route_movie_main_without_year(tmp_path):
    dl = Download(title="Untitled Doc", year=None, media_type=MediaType.MOVIE)
    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = "/plex/movies"
        dest = _route_movie_main(tmp_path / "doc.mkv", dl)
    assert str(dest) == "/plex/movies/Untitled Doc/Untitled Doc.mkv"


def test_route_movie_extra_to_featurettes(tmp_path):
    dl = Download(title="Birth", year=2004, media_type=MediaType.MOVIE)
    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = "/plex/movies"
        dest = _route_movie_extra(tmp_path / "Trailer.mkv", dl)
    assert str(dest) == "/plex/movies/Birth (2004)/Featurettes/Trailer.mkv"


def test_route_tv_zero_pads(tmp_path):
    dl = Download(title="Gen V", media_type=MediaType.TV)
    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_TV_DIR = "/plex/tv"
        dest = _route_tv(tmp_path / "Gen.V.S02E06.1080p.mkv", dl)
    assert str(dest) == "/plex/tv/Gen V/Season 02/Gen V - S02E06.mkv"


def test_route_tv_returns_none_on_missing_se(tmp_path):
    dl = Download(title="Show", media_type=MediaType.TV)
    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_TV_DIR = "/plex/tv"
        dest = _route_tv(tmp_path / "random.mkv", dl)
    assert dest is None


# --- organize_download integration ---

def test_organize_movie_with_main_and_extras(db_session, tmp_path):
    """Birth (2004) style: main feature + 3 extras → main to root, extras to Featurettes."""
    main_src = tmp_path / "Birth.2004.1080p.mkv"
    main_src.write_text("main")
    t_src = tmp_path / "Trailer.mkv"
    t_src.write_text("trailer")
    m_src = tmp_path / "Making Birth.mkv"
    m_src.write_text("making")

    plex = tmp_path / "plex"
    plex.mkdir()

    dl = Download(title="Birth", year=2004, media_type=MediaType.MOVIE)
    dl.files.append(DownloadFile(url="u1", name=main_src.name, is_extra=False))
    dl.files.append(DownloadFile(url="u2", name=t_src.name, is_extra=True))
    dl.files.append(DownloadFile(url="u3", name=m_src.name, is_extra=True))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(plex)
        paths = organize_download(dl, [main_src, t_src, m_src])

    assert paths[0] == str(plex / "Birth (2004)" / "Birth (2004).mkv")
    assert paths[1] == str(plex / "Birth (2004)" / "Featurettes" / "Trailer.mkv")
    assert paths[2] == str(plex / "Birth (2004)" / "Featurettes" / "Making Birth.mkv")

    assert (plex / "Birth (2004)" / "Birth (2004).mkv").exists()
    assert (plex / "Birth (2004)" / "Featurettes" / "Trailer.mkv").exists()
    assert not main_src.exists()  # moved


def test_organize_tv_writes_canonical_episode_names(db_session, tmp_path):
    e1 = tmp_path / "Gen.V.S02E01.1080p.mkv"
    e1.write_text("e1")
    e2 = tmp_path / "Gen.V.S02E02.1080p.mkv"
    e2.write_text("e2")

    plex = tmp_path / "tv"
    plex.mkdir()

    dl = Download(title="Gen V", media_type=MediaType.TV)
    dl.files.append(DownloadFile(url="u1", name=e1.name))
    dl.files.append(DownloadFile(url="u2", name=e2.name))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_TV_DIR = str(plex)
        paths = organize_download(dl, [e1, e2])

    assert paths[0] == str(plex / "Gen V" / "Season 02" / "Gen V - S02E01.mkv")
    assert paths[1] == str(plex / "Gen V" / "Season 02" / "Gen V - S02E02.mkv")
    assert (plex / "Gen V" / "Season 02" / "Gen V - S02E01.mkv").exists()


def test_organize_tv_per_file_failure_does_not_abort(db_session, tmp_path):
    """A TV file with no S/E is marked failed; siblings still organise."""
    good = tmp_path / "Show.S01E01.1080p.mkv"
    good.write_text("good")
    bad = tmp_path / "random.mkv"
    bad.write_text("bad")

    plex = tmp_path / "tv"
    plex.mkdir()

    dl = Download(title="Show", media_type=MediaType.TV)
    f1 = DownloadFile(url="u1", name=good.name)
    f2 = DownloadFile(url="u2", name=bad.name)
    dl.files.extend([f1, f2])
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_TV_DIR = str(plex)
        paths = organize_download(dl, [good, bad])

    assert paths[0] is not None
    assert paths[1] is None  # bad file skipped
    assert f2.status == FileStatus.FAILED
    assert "season/episode" in f2.error_message.lower()


def test_organize_movie_year_less_fallback(db_session, tmp_path):
    """No year → folder is just <Title> and filename is <Title>.<ext>."""
    src = tmp_path / "raw_dump.mkv"
    src.write_text("data")
    plex = tmp_path / "plex"
    plex.mkdir()

    dl = Download(title="Unknown Origin", year=None, media_type=MediaType.MOVIE)
    dl.files.append(DownloadFile(url="u1", name=src.name, is_extra=False))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(plex)
        paths = organize_download(dl, [src])

    assert paths[0] == str(plex / "Unknown Origin" / "Unknown Origin.mkv")


# --- Archive extraction (mocked) ---

@patch("megaqueue.organiser._extract_archive")
def test_organize_with_archive_calls_extractor(mock_extract, db_session, tmp_path):
    """An archive source triggers _extract_archive and then routes the largest extracted file."""
    archive = tmp_path / "movie.rar"
    archive.write_text("placeholder")

    def fake_extract(src, dest):
        # Simulate extraction: drop one .mkv into dest.
        (dest / "Inception.2010.1080p.mkv").write_text("video")
    mock_extract.side_effect = fake_extract

    plex = tmp_path / "plex"
    plex.mkdir()

    dl = Download(title="Inception", year=2010, media_type=MediaType.MOVIE)
    dl.files.append(DownloadFile(url="u1", name="movie.rar", is_extra=False))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(plex)
        paths = organize_download(dl, [archive])

    mock_extract.assert_called_once()
    assert paths[0] == str(plex / "Inception (2010)" / "Inception (2010).mkv")


# --- Move retry on transient file locks (WinError 32) ---

@patch("megaqueue.organiser.time.sleep")
def test_move_retries_on_locked_file_then_succeeds(mock_sleep, tmp_path):
    """A transient OSError (file locked) is retried; a later success completes the move."""
    src = tmp_path / "src.mkv"
    src.write_text("video")
    dest = tmp_path / "out" / "dest.mkv"

    real_move = shutil.move
    calls = {"n": 0}

    def flaky_move(s, d):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError(32, "The process cannot access the file")
        return real_move(s, d)

    with patch("megaqueue.organiser.shutil.move", side_effect=flaky_move):
        result = _move(src, dest)

    assert result == str(dest)
    assert dest.exists()
    assert calls["n"] == 2
    mock_sleep.assert_called_once()  # slept once between the two attempts


@patch("megaqueue.organiser.time.sleep")
def test_move_raises_after_exhausting_retries(mock_sleep, tmp_path):
    """A persistently locked file raises the last OSError after all retries."""
    src = tmp_path / "src.mkv"
    src.write_text("video")
    dest = tmp_path / "out" / "dest.mkv"

    with patch("megaqueue.organiser.shutil.move",
               side_effect=OSError(32, "still locked")) as mock_move:
        with pytest.raises(OSError):
            _move(src, dest)

    assert mock_move.call_count == 5  # MOVE_RETRIES


# --- _check_unrar ---

def test_check_unrar_raises_when_not_on_path():
    with patch("megaqueue.organiser.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="not found on PATH"):
            _check_unrar()


def test_check_unrar_passes_when_available():
    with patch("megaqueue.organiser.shutil.which", return_value="/usr/bin/unrar"):
        _check_unrar()


# --- _has_media_files ---

def test_has_media_files_with_video(tmp_path):
    (tmp_path / "movie.mkv").touch()
    assert _has_media_files(tmp_path) is True


def test_has_media_files_with_subtitle_only(tmp_path):
    (tmp_path / "movie.srt").touch()
    assert _has_media_files(tmp_path) is True


def test_has_media_files_with_non_media_only(tmp_path):
    (tmp_path / "readme.txt").touch()
    (tmp_path / "info.nfo").touch()
    assert _has_media_files(tmp_path) is False


def test_has_media_files_empty_dir(tmp_path):
    assert _has_media_files(tmp_path) is False


# --- Post-extraction validation ---

@patch("megaqueue.organiser._check_unrar")
def test_extract_archive_raises_when_no_files_produced(mock_check, tmp_path):
    """extractall() succeeds but produces nothing → RuntimeError with diagnostics."""
    archive = tmp_path / "movie.rar"
    archive.write_text("fake")
    dest = tmp_path / "out"
    dest.mkdir()

    mock_rf = MagicMock()
    mock_rf_cm = MagicMock()
    mock_rf_cm.extractall = MagicMock()
    mock_rf.RarFile.return_value.__enter__ = MagicMock(return_value=mock_rf_cm)
    mock_rf.RarFile.return_value.__exit__ = MagicMock(return_value=False)

    import sys
    with patch.dict(sys.modules, {"rarfile": mock_rf}):
        from megaqueue.organiser import _extract_archive
        with pytest.raises(RuntimeError, match="produced no files"):
            _extract_archive(archive, dest)


# --- Pre-extracted directory support ---

def test_organize_with_pre_extracted_directory(db_session, tmp_path):
    """A pre-extracted directory routes its media files like an extracted archive."""
    pre_extracted = tmp_path / "H2OBoy"
    pre_extracted.mkdir()
    (pre_extracted / "The Waterboy (1998).mkv").write_text("video content")

    plex = tmp_path / "plex"
    plex.mkdir()

    dl = Download(title="The Waterboy", year=1998, media_type=MediaType.MOVIE)
    dl.files.append(DownloadFile(url="u1", name="H2OBoy.rar", is_extra=False))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(plex)
        paths = organize_download(dl, [pre_extracted], pre_extracted=[True])

    assert paths[0] == str(plex / "The Waterboy (1998)" / "The Waterboy (1998).mkv")
    assert (plex / "The Waterboy (1998)" / "The Waterboy (1998).mkv").exists()


def test_organize_pre_extracted_removes_empty_dir(db_session, tmp_path):
    """An emptied pre-extracted directory is cleaned up."""
    pre_extracted = tmp_path / "movie"
    pre_extracted.mkdir()
    (pre_extracted / "film.mkv").write_text("video")

    plex = tmp_path / "plex"
    plex.mkdir()

    dl = Download(title="Film", year=2020, media_type=MediaType.MOVIE)
    dl.files.append(DownloadFile(url="u1", name="movie.rar", is_extra=False))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(plex)
        organize_download(dl, [pre_extracted], pre_extracted=[True])

    assert not pre_extracted.exists()


def test_organize_pre_extracted_preserves_non_empty_dir(db_session, tmp_path):
    """A pre-extracted dir with leftover non-media files is NOT deleted."""
    pre_extracted = tmp_path / "movie"
    pre_extracted.mkdir()
    (pre_extracted / "film.mkv").write_text("video")
    (pre_extracted / "readme.txt").write_text("info")

    plex = tmp_path / "plex"
    plex.mkdir()

    dl = Download(title="Film", year=2020, media_type=MediaType.MOVIE)
    dl.files.append(DownloadFile(url="u1", name="movie.rar", is_extra=False))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(plex)
        organize_download(dl, [pre_extracted], pre_extracted=[True])

    assert pre_extracted.exists()
    assert (pre_extracted / "readme.txt").exists()


def test_organize_pre_extracted_raises_on_no_media(db_session, tmp_path):
    pre_extracted = tmp_path / "movie"
    pre_extracted.mkdir()
    (pre_extracted / "readme.txt").write_text("info")

    plex = tmp_path / "plex"
    plex.mkdir()

    dl = Download(title="Film", year=2020, media_type=MediaType.MOVIE)
    dl.files.append(DownloadFile(url="u1", name="movie.rar", is_extra=False))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_MOVIES_DIR = str(plex)
        with pytest.raises(RuntimeError, match="no media files"):
            organize_download(dl, [pre_extracted], pre_extracted=[True])


# --- Destination already exists (skip move) ---

def test_organize_skips_move_when_destination_exists(db_session, tmp_path):
    """If the destination file already exists on disk, the move is skipped."""
    src = tmp_path / "Gen.V.S02E01.1080p.mkv"
    src.write_text("new")

    plex = tmp_path / "tv"
    plex.mkdir()
    dest_dir = plex / "Gen V" / "Season 02"
    dest_dir.mkdir(parents=True)
    existing = dest_dir / "Gen V - S02E01.mkv"
    existing.write_text("already here")

    dl = Download(title="Gen V", media_type=MediaType.TV)
    dl.files.append(DownloadFile(url="u1", name=src.name))
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_TV_DIR = str(plex)
        paths = organize_download(dl, [src])

    assert paths[0] == str(existing)
    assert existing.read_text() == "already here"
    assert src.exists()


def test_organize_with_leaf_files_param(db_session, tmp_path):
    """organize_download accepts explicit leaf_files for re-check partial organise."""
    src = tmp_path / "Gen.V.S02E03.1080p.mkv"
    src.write_text("e3")

    plex = tmp_path / "tv"
    plex.mkdir()

    dl = Download(title="Gen V", media_type=MediaType.TV)
    f1 = DownloadFile(url="u1", name="Gen.V.S02E01.1080p.mkv")
    f2 = DownloadFile(url="u2", name="Gen.V.S02E03.1080p.mkv")
    dl.files.extend([f1, f2])
    db_session.add(dl)
    db_session.commit()

    with patch("megaqueue.organiser.config") as mock_config:
        mock_config.PLEX_TV_DIR = str(plex)
        paths = organize_download(dl, [src], leaf_files=[f2])

    assert len(paths) == 1
    assert paths[0] is not None
    assert (plex / "Gen V" / "Season 02" / "Gen V - S02E03.mkv").exists()
