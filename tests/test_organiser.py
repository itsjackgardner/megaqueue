from unittest.mock import patch, MagicMock

import pytest

from megaqueue.enums import FileStatus, MediaType
from megaqueue.models import Download, DownloadFile
from megaqueue.organiser import (
    _is_archive,
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
