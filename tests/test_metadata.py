from megaqueue.enums import MediaType, MetadataConfidence, MetadataSource
from megaqueue.metadata import (
    parse_filename,
    refresh,
    _aggregate_movie,
    _aggregate_tv,
    _score_confidence,
    _vote_type,
)
from megaqueue.models import Download, DownloadFile


# --- parse_filename ---

def test_parse_movie_with_year_and_quality():
    p = parse_filename("Birth.2004.Criterion.1080p.BluRay.x265.HEVC.FLAC-SARTRE.mkv")
    assert p["title"] == "Birth"
    assert p["year"] == 2004
    assert p["type"] == "movie"
    assert p["screen_size"] == "1080p"
    assert "source" in p


def test_parse_episode_with_se():
    p = parse_filename("Gen.V.S02E06.1080p.10bit.WEBRip.6CH.x265.HEVC-PSA.mkv")
    assert p["title"] == "Gen V"
    assert p["season"] == 2
    assert p["episode"] == 6
    assert p["type"] == "episode"


def test_parse_bare_extra_returns_no_year_no_quality():
    p = parse_filename("Trailer.mkv")
    assert p.get("year") is None
    assert p.get("screen_size") is None
    assert p.get("source") is None


def test_parse_empty_string_returns_empty_dict():
    assert parse_filename("") == {}


# --- _vote_type ---

def test_vote_type_all_episodes():
    parsed = [{"type": "episode"}] * 5
    assert _vote_type(parsed) == MediaType.TV


def test_vote_type_all_movies():
    parsed = [{"type": "movie"}] * 5
    assert _vote_type(parsed) == MediaType.MOVIE


def test_vote_type_mixed_returns_none():
    parsed = [{"type": "movie"}, {"type": "movie"}, {"type": "episode"}, {"type": "episode"}]
    assert _vote_type(parsed) is None


def test_vote_type_empty_returns_none():
    assert _vote_type([]) is None


# --- _aggregate_movie ---

def _df(name, size=0, is_extra=False):
    return DownloadFile(url="u", name=name, total_bytes=size, is_extra=is_extra)


def test_aggregate_movie_picks_main_feature_by_year_and_quality():
    """The Birth (2004) case: main feature has year+quality, extras don't."""
    leaf_files = [
        _df("Birth.2004.Criterion.1080p.BluRay.mkv", size=8_400_000_000),
        _df("Trailer.mkv", size=17_000_000),
        _df("Making Birth.mkv", size=232_000_000),
    ]
    parsed = [parse_filename(f.name) for f in leaf_files]
    title, year = _aggregate_movie(parsed, leaf_files)

    assert title == "Birth"
    assert year == 2004
    assert leaf_files[0].is_extra is False
    assert leaf_files[1].is_extra is True
    assert leaf_files[2].is_extra is True


def test_aggregate_movie_largest_wins_when_no_year():
    """Fallback: when no file has year+quality, the largest wins as main feature."""
    leaf_files = [
        _df("small.mkv", size=100_000),
        _df("big.mkv", size=5_000_000_000),
        _df("medium.mkv", size=500_000_000),
    ]
    parsed = [parse_filename(f.name) for f in leaf_files]
    title, year = _aggregate_movie(parsed, leaf_files)

    assert year is None
    assert leaf_files[1].is_extra is False
    assert leaf_files[0].is_extra is True
    assert leaf_files[2].is_extra is True


def test_aggregate_movie_largest_breaks_quality_tie():
    """Two files with year+quality → the larger one is the main feature."""
    leaf_files = [
        _df("Movie.2024.1080p.BluRay.mkv", size=800_000_000),
        _df("Movie.2024.4K.BluRay.mkv", size=12_000_000_000),
    ]
    parsed = [parse_filename(f.name) for f in leaf_files]
    _aggregate_movie(parsed, leaf_files)
    assert leaf_files[1].is_extra is False
    assert leaf_files[0].is_extra is True


# --- _aggregate_tv ---

def test_aggregate_tv_majority_title():
    parsed = [
        {"type": "episode", "title": "Gen V", "season": 2, "episode": 1},
        {"type": "episode", "title": "Gen V", "season": 2, "episode": 2},
        {"type": "episode", "title": "Gen V", "season": 2, "episode": 3},
    ]
    title, season = _aggregate_tv(parsed)
    assert title == "Gen V"
    assert season == 2


def test_aggregate_tv_empty_returns_nones():
    assert _aggregate_tv([]) == (None, None)


# --- _score_confidence ---

def test_score_confidence_tv_all_se_and_consistent_title_is_high():
    parsed = [
        {"season": 1, "episode": 1, "title": "Show", "type": "episode"},
        {"season": 1, "episode": 2, "title": "Show", "type": "episode"},
        {"season": 1, "episode": 3, "title": "Show", "type": "episode"},
    ]
    assert _score_confidence(MediaType.TV, "Show", None, parsed) == MetadataConfidence.HIGH


def test_score_confidence_tv_missing_se_on_any_is_low():
    parsed = [
        {"season": 1, "episode": 1, "title": "Show", "type": "episode"},
        {"title": "Show", "type": "episode"},  # missing season/episode
    ]
    assert _score_confidence(MediaType.TV, "Show", None, parsed) == MetadataConfidence.LOW


def test_score_confidence_movie_with_year_is_high():
    parsed = [{"title": "Birth", "year": 2004, "type": "movie", "screen_size": "1080p"}]
    assert _score_confidence(MediaType.MOVIE, "Birth", 2004, parsed) == MetadataConfidence.HIGH


def test_score_confidence_movie_without_year_is_low():
    parsed = [{"title": "Movie", "type": "movie"}]
    assert _score_confidence(MediaType.MOVIE, "Movie", None, parsed) == MetadataConfidence.LOW


def test_score_confidence_unknown_media_type_is_low():
    parsed = [{"type": "movie"}, {"type": "episode"}]
    assert _score_confidence(None, "thing", None, parsed) == MetadataConfidence.LOW


# --- refresh ---

def test_refresh_movie_writes_metadata_and_flags_extras(db_session):
    """End-to-end: Birth-like folder triggers movie aggregation, sets confidence high."""
    dl = Download(metadata_confidence=MetadataConfidence.LOW)
    dl.files.append(DownloadFile(url="u1", name="Birth.2004.Criterion.1080p.BluRay.mkv",
                                  total_bytes=8_000_000_000))
    dl.files.append(DownloadFile(url="u2", name="Trailer.mkv", total_bytes=17_000_000))
    dl.files.append(DownloadFile(url="u3", name="Making Birth.mkv", total_bytes=232_000_000))
    db_session.add(dl)
    db_session.commit()

    refresh(dl)

    assert dl.title == "Birth"
    assert dl.year == 2004
    assert dl.media_type == MediaType.MOVIE
    assert dl.metadata_confidence == MetadataConfidence.HIGH
    assert dl.metadata_source == MetadataSource.GUESSIT

    leaves = dl.leaf_files
    main = next(f for f in leaves if f.name.startswith("Birth"))
    assert main.is_extra is False
    extras = [f for f in leaves if f.name != main.name]
    assert all(f.is_extra for f in extras)


def test_refresh_tv_writes_title_and_high_confidence(db_session):
    dl = Download(metadata_confidence=MetadataConfidence.LOW)
    for i in range(1, 4):
        dl.files.append(DownloadFile(url=f"u{i}", name=f"Gen.V.S02E0{i}.1080p.mkv"))
    db_session.add(dl)
    db_session.commit()

    refresh(dl)

    assert dl.title == "Gen V"
    assert dl.media_type == MediaType.TV
    assert dl.metadata_confidence == MetadataConfidence.HIGH
    assert all(f.is_extra is False for f in dl.leaf_files)


def test_refresh_preserves_user_metadata(db_session):
    """When metadata_source=user, refresh only updates is_extra, not title/year/media_type."""
    dl = Download(title="UserTitle", year=1999, media_type=MediaType.MOVIE,
                  metadata_source=MetadataSource.USER,
                  metadata_confidence=MetadataConfidence.HIGH)
    dl.files.append(DownloadFile(url="u1", name="Birth.2004.1080p.BluRay.mkv",
                                  total_bytes=8_000_000_000))
    dl.files.append(DownloadFile(url="u2", name="Trailer.mkv", total_bytes=17_000_000))
    db_session.add(dl)
    db_session.commit()

    refresh(dl)

    # User values preserved.
    assert dl.title == "UserTitle"
    assert dl.year == 1999
    assert dl.media_type == MediaType.MOVIE
    assert dl.metadata_source == MetadataSource.USER

    # is_extra still flows from filenames.
    leaves = dl.leaf_files
    main = next(f for f in leaves if f.name.startswith("Birth"))
    assert main.is_extra is False


def test_refresh_no_named_files_is_noop(db_session):
    """No leaf files have names yet → refresh writes nothing."""
    dl = Download(metadata_confidence=MetadataConfidence.LOW)
    dl.files.append(DownloadFile(url="u1", name=None))
    db_session.add(dl)
    db_session.commit()

    refresh(dl)

    assert dl.title is None
    assert dl.metadata_source is None
