"""Filename-driven metadata resolution via guessit.

Runs on every poll tick where a DownloadFile name lands. Aggregates per-file
parses into the parent Download's title/year/media_type and flags movie
featurettes via is_extra. Confidence scoring decides whether the lifecycle
can proceed to PROCESSING or must enter NEEDS_REVIEW.

User-supplied values (metadata_source == USER) are preserved; only is_extra
flags get re-flowed from filenames in that case.
"""

import logging
from collections import Counter

from guessit import guessit as _guessit

from megaqueue.enums import MediaType, MetadataConfidence, MetadataSource
from megaqueue.models import db_session

log = logging.getLogger(__name__)

# Tags that signal a "main feature" rather than a featurette.
_QUALITY_TAGS = ("screen_size", "source", "video_codec")


def parse_filename(name):
    """Return a plain dict with the guessit fields we care about.

    Wraps `guessit.guessit` and converts its `MatchesDict` to a regular dict
    so downstream code doesn't have to deal with guessit-specific types.
    """
    if not name:
        return {}
    result = _guessit(name)
    out = {}
    for key in ("title", "year", "season", "episode", "type",
                "screen_size", "source", "video_codec"):
        if key in result:
            out[key] = result[key]
    return out


def _aggregate_tv(parsed_per_file):
    """Vote on TV series title across episode-typed files.

    Returns (title, season_hint). All TV files keep is_extra=False.
    """
    titles = [p.get("title") for p in parsed_per_file if p.get("title")]
    if not titles:
        return None, None
    title = Counter(titles).most_common(1)[0][0]
    seasons = [p.get("season") for p in parsed_per_file if p.get("season") is not None]
    season_hint = Counter(seasons).most_common(1)[0][0] if seasons else None
    return title, season_hint


def _aggregate_movie(parsed_per_file, leaf_files):
    """Pick the movie main feature and tag the rest as extras.

    Main feature = file whose guessit result includes a year AND at least one
    quality tag (screen_size / source / video_codec). Tiebreak by largest
    total_bytes. If no file matches, fall back to the largest file.

    Returns (title, year). Mutates `is_extra` on every leaf in `leaf_files`.
    """
    candidates = []
    for i, p in enumerate(parsed_per_file):
        if p.get("year") and any(p.get(k) for k in _QUALITY_TAGS):
            candidates.append((i, leaf_files[i].total_bytes or 0))

    if candidates:
        candidates.sort(key=lambda x: -x[1])
        main_idx = candidates[0][0]
    elif leaf_files:
        # Fallback: largest file is the main feature.
        sized = [(i, leaf_files[i].total_bytes or 0) for i in range(len(leaf_files))]
        sized.sort(key=lambda x: -x[1])
        main_idx = sized[0][0]
    else:
        return None, None

    main_parsed = parsed_per_file[main_idx]
    title = main_parsed.get("title")
    year = main_parsed.get("year")

    for i, df in enumerate(leaf_files):
        df.is_extra = (i != main_idx)

    return title, year


def _score_confidence(media_type, title, year, parsed_per_file):
    """Return MetadataConfidence.HIGH or LOW per spec rules.

    HIGH when either:
      - TV: every file has both season and episode AND >=80% of files agree
        on the same title;
      - Movie: a main feature was selected via the year+quality rule (i.e.
        title and year are both set on the Download).

    LOW in all other cases.
    """
    if not parsed_per_file:
        return MetadataConfidence.LOW
    if not title:
        return MetadataConfidence.LOW

    if media_type == MediaType.TV:
        if not all(p.get("season") is not None and p.get("episode") is not None
                   for p in parsed_per_file):
            return MetadataConfidence.LOW
        titles = [p.get("title") for p in parsed_per_file if p.get("title")]
        if not titles:
            return MetadataConfidence.LOW
        most_common_count = Counter(titles).most_common(1)[0][1]
        if most_common_count / len(parsed_per_file) < 0.8:
            return MetadataConfidence.LOW
        return MetadataConfidence.HIGH

    if media_type == MediaType.MOVIE:
        # Movie confidence requires a year on the main feature.
        if year is None:
            return MetadataConfidence.LOW
        return MetadataConfidence.HIGH

    return MetadataConfidence.LOW


def _vote_type(parsed_per_file):
    """Decide whether the Download is movie or TV based on guessit per-file types.

    >50% episodes -> TV. >50% movies -> movie. Otherwise None (mixed).
    """
    types = [p.get("type") for p in parsed_per_file if p.get("type")]
    if not types:
        return None
    counts = Counter(types)
    total = len(types)
    if counts.get("episode", 0) / total > 0.5:
        return MediaType.TV
    if counts.get("movie", 0) / total > 0.5:
        return MediaType.MOVIE
    return None


def refresh(download):
    """Re-aggregate metadata from current filenames for a Download.

    Reads every leaf DownloadFile that has a populated name, runs guessit on
    each, and:
      - If metadata_source == USER: only updates is_extra on files; never
        overwrites title/year/media_type.
      - Otherwise: writes the aggregated title/year/media_type and the
        scored confidence, with metadata_source = GUESSIT.

    Does NOT commit. The caller (sync.update_file_from_megabasterd) is
    responsible for committing in its own transaction.
    """
    leaf_files = [df for df in download.leaf_files if df.name]
    if not leaf_files:
        return

    parsed_per_file = [parse_filename(df.name) for df in leaf_files]

    media_type = _vote_type(parsed_per_file)

    if media_type == MediaType.MOVIE:
        title, year = _aggregate_movie(parsed_per_file, leaf_files)
    elif media_type == MediaType.TV:
        title, _ = _aggregate_tv(parsed_per_file)
        year = None
        for df in leaf_files:
            df.is_extra = False
    else:
        # Mixed/unknown type: clear is_extra and don't guess at title/year.
        title = None
        year = None
        for df in leaf_files:
            df.is_extra = False

    if download.metadata_source == MetadataSource.USER:
        # Honour user-supplied title/year/media_type; only is_extra flags
        # (set above) flow back into the DB.
        return

    download.title = title
    download.year = year
    download.media_type = media_type
    download.metadata_confidence = _score_confidence(media_type, title, year, parsed_per_file)
    download.metadata_source = MetadataSource.GUESSIT
