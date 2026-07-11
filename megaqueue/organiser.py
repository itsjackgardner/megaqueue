"""Hand-rolled organiser: parses filenames with guessit, routes into Plex folders.

Replaces FileBot. Movies → `<PLEX_MOVIES_DIR>/<Title> (<Year>)/<Title> (<Year>).<ext>`;
movie extras → `<PLEX_MOVIES_DIR>/<Title> (<Year>)/Featurettes/<original-name>`;
TV episodes → `<PLEX_TV_DIR>/<Title>/Season <NN>/<Title> - S<NN>E<NN>.<ext>`.

Archive extraction uses rarfile (needs `unrar` system binary), stdlib zipfile,
and py7zr.
"""

import logging
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

from megaqueue import config
from megaqueue.enums import FileStatus, MediaType
from megaqueue.metadata import parse_filename

log = logging.getLogger(__name__)

ARCHIVE_EXTENSIONS = {".rar", ".zip", ".7z", ".001"}

# Windows can briefly refuse a move (WinError 32) while megabasterd releases its
# handle, or while Plex/antivirus scans the new file. Retry before giving up.
MOVE_RETRIES = 6
MOVE_RETRY_BASE_DELAY = 2  # seconds; doubles each attempt (2, 4, 8, 16, 32)


def _is_archive(path):
    return path.suffix.lower() in ARCHIVE_EXTENSIONS


def _sanitize(name):
    """Strip characters that are illegal in Windows/Plex paths."""
    return re.sub(r"[<>:\"/\\|?*]", "", name).strip()


def _extract_archive(archive_path, dest_dir):
    """Extract one archive into dest_dir using the right library for its format."""
    ext = archive_path.suffix.lower()
    if ext == ".zip":
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(dest_dir)
    elif ext == ".7z":
        import py7zr
        with py7zr.SevenZipFile(archive_path, mode="r") as sz:
            sz.extractall(path=dest_dir)
    elif ext in (".rar", ".001"):
        import rarfile
        with rarfile.RarFile(archive_path) as rf:
            rf.extractall(dest_dir)
    else:
        raise RuntimeError(f"Unsupported archive type: {archive_path}")


def _route_movie_main(file_path, download):
    """Compute the Plex destination for the movie's main feature."""
    title = _sanitize(download.title or file_path.stem)
    if download.year:
        folder = f"{title} ({download.year})"
        new_name = f"{title} ({download.year}){file_path.suffix}"
    else:
        folder = title
        new_name = f"{title}{file_path.suffix}"
    return Path(config.PLEX_MOVIES_DIR) / folder / new_name


def _route_movie_extra(file_path, download):
    """Compute the Plex destination for a movie extra (featurette/trailer)."""
    title = _sanitize(download.title or "Unknown")
    if download.year:
        folder = f"{title} ({download.year})"
    else:
        folder = title
    return Path(config.PLEX_MOVIES_DIR) / folder / "Featurettes" / file_path.name


def _route_tv(file_path, download):
    """Compute the Plex destination for a TV episode. Returns None if S/E missing."""
    parsed = parse_filename(file_path.name)
    season = parsed.get("season")
    episode = parsed.get("episode")
    if season is None or episode is None:
        return None
    title = _sanitize(download.title or parsed.get("title") or file_path.stem)
    new_name = f"{title} - S{season:02d}E{episode:02d}{file_path.suffix}"
    return Path(config.PLEX_TV_DIR) / title / f"Season {season:02d}" / new_name


def _route(file_path, download, leaf_file):
    """Pick the Plex destination for one file. Returns Path or None.

    None means we couldn't determine a destination (e.g. TV file without S/E).
    The caller marks the leaf record as failed in that case.
    """
    if download.media_type == MediaType.MOVIE:
        if leaf_file is not None and leaf_file.is_extra:
            return _route_movie_extra(file_path, download)
        return _route_movie_main(file_path, download)
    if download.media_type == MediaType.TV:
        return _route_tv(file_path, download)
    raise RuntimeError(
        f"Cannot organise download {download.id}: media_type is not set"
    )


def _move(src, dest):
    """Move src to dest, creating parent dirs and returning dest as a string.

    Retries on transient OS-level file locks (notably Windows WinError 32):
    even after megabasterd is told to release the download, the handle, the
    Plex scanner, or antivirus can briefly keep the file open.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err = None
    for attempt in range(1, MOVE_RETRIES + 1):
        try:
            shutil.move(str(src), str(dest))
            log.info("Moved %s -> %s", src, dest)
            return str(dest)
        except OSError as e:
            last_err = e
            delay = MOVE_RETRY_BASE_DELAY * (2 ** (attempt - 1))
            log.warning(
                "Move attempt %d/%d failed for '%s': %s — retrying in %ds",
                attempt, MOVE_RETRIES, src, e, delay,
            )
            if attempt < MOVE_RETRIES:
                time.sleep(delay)
    raise last_err


def _organize_one(file_path, download, leaf_file):
    """Route + move one file. Returns the destination path string, or None on per-file failure.

    Per-file failure (TV without S/E) marks the leaf as FAILED but does not
    abort the run.
    """
    dest = _route(file_path, download, leaf_file)
    if dest is None:
        if leaf_file is not None:
            leaf_file.status = FileStatus.FAILED
            leaf_file.error_message = "No season/episode detected"
        log.warning("Skipping '%s' — no destination resolved", file_path.name)
        return None
    return _move(file_path, dest)


def organize_download(download, source_paths):
    """Organise files for a finished download.

    Args:
        download: the Download row (already PROCESSING status). Has title,
            year (optional), media_type, and a leaf_files list whose
            is_extra flags drive movie routing.
        source_paths: list of Path objects, one per leaf file (same order
            as download.leaf_files).

    Returns the list of final destination path strings aligned by index
    with download.leaf_files. For archive sources, the leaf's file_path
    is set to the first extracted file's final destination; subsequent
    extracted files are routed individually but not threaded back into
    the DB (Plex picks them up by folder scan).
    """
    leaf_files = download.leaf_files
    final_paths = [None] * len(leaf_files)

    temp_dir = Path(tempfile.mkdtemp(prefix="megaqueue_"))
    try:
        for i, src in enumerate(source_paths):
            leaf = leaf_files[i] if i < len(leaf_files) else None

            if _is_archive(src):
                log.info("Extracting archive '%s'", src.name)
                _extract_archive(src, temp_dir)
                extracted = sorted(
                    [p for p in temp_dir.rglob("*") if p.is_file()],
                    key=lambda p: -p.stat().st_size,
                )
                if not extracted:
                    raise RuntimeError(f"Archive {src.name} produced no files")
                first = _organize_one(extracted[0], download, leaf)
                final_paths[i] = first
                for extra in extracted[1:]:
                    _organize_one(extra, download, None)
                # Source archive isn't moved; megabasterd's download dir cleanup is its problem.
            else:
                final_paths[i] = _organize_one(src, download, leaf)

        return final_paths

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
