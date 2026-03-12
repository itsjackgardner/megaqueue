import logging
import re
import shutil
import tempfile
from pathlib import Path

import config

log = logging.getLogger(__name__)

ARCHIVE_EXTENSIONS = {".rar", ".zip", ".7z", ".001"}
SEASON_PATTERN = re.compile(r"[Ss](\d{1,2})[Ee]\d{1,2}")


def _detect_season(filename):
    """Extract season number from filename like S03E05. Returns None if not found."""
    match = SEASON_PATTERN.search(filename)
    if match:
        return int(match.group(1))
    return None


def _is_archive(path):
    """Check if a file is an archive that should be extracted."""
    return path.suffix.lower() in ARCHIVE_EXTENSIONS


def _collect_files(source_paths):
    """Collect all files from source paths. Directories are walked (non-recursive).

    Returns list of Path objects for all individual files.
    Raises FileNotFoundError if any source path does not exist.
    """
    files = []
    for src in source_paths:
        if not src.exists():
            raise FileNotFoundError(f"Source path does not exist: {src}")
        if src.is_dir():
            files.extend(f for f in src.iterdir() if f.is_file())
        else:
            files.append(src)
    return files


def _extract_archives(all_files, temp_dir):
    """Detect and extract archives from collected files.

    If archive parts are found in multiple directories, consolidates them into
    a temp directory before extraction.

    Returns (extracted_files, non_archive_files) — two lists of Path objects.
    """
    archives = [f for f in all_files if _is_archive(f)]
    non_archives = [f for f in all_files if not _is_archive(f)]

    if not archives:
        return [], non_archives

    # Check if archives span multiple directories
    archive_dirs = {f.parent for f in archives}
    if len(archive_dirs) > 1:
        # Consolidate all archive parts into temp dir
        consolidation_dir = Path(temp_dir) / "_consolidated"
        consolidation_dir.mkdir(parents=True, exist_ok=True)
        for archive in archives:
            shutil.copy2(str(archive), str(consolidation_dir / archive.name))
        # Use the first archive in the consolidated dir as the entry point
        entry_archive = consolidation_dir / archives[0].name
    else:
        entry_archive = archives[0]

    extract_dir = Path(temp_dir) / "_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        import patoolib
        patoolib.extract_archive(str(entry_archive), outdir=str(extract_dir))
    except ImportError:
        log.warning("patool not available, trying 7z subprocess")
        import subprocess
        subprocess.run(
            ["7z", "x", str(entry_archive), f"-o{extract_dir}", "-y"],
            check=True,
            capture_output=True,
        )

    extracted = [f for f in extract_dir.rglob("*") if f.is_file()]
    return extracted, non_archives


def _move_file(src, dest_dir, filename):
    """Move a file to dest_dir, creating directories as needed. Returns destination path string."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    shutil.move(str(src), str(dest))
    log.info("Moved %s -> %s", src, dest)
    return str(dest)


def _route_movie(file_path, download):
    """Move a movie file to PLEX_MOVIES_DIR/<Title> (<Year>)/"""
    if download.year:
        folder_name = f"{download.title} ({download.year})"
    else:
        folder_name = download.title

    dest_dir = Path(config.PLEX_MOVIES_DIR) / folder_name
    return _move_file(file_path, dest_dir, file_path.name)


def _route_tv(file_path, download):
    """Move a TV file to PLEX_TV_DIR/<Title>/Season XX/ based on filename."""
    season = _detect_season(file_path.name)
    base_dir = Path(config.PLEX_TV_DIR) / download.title

    if season is not None:
        dest_dir = base_dir / f"Season {season:02d}"
    else:
        dest_dir = base_dir

    return _move_file(file_path, dest_dir, file_path.name)


def organize_download(download, source_paths):
    """Organize downloaded files into Plex library folders.

    Args:
        download: Download model instance with title, year, media_type.
        source_paths: List of Path objects pointing to downloaded files/directories.

    Returns list of final destination path strings.
    """
    # Phase 1: Discovery — collect all files from source paths
    all_files = _collect_files(source_paths)
    if not all_files:
        raise FileNotFoundError("No files found in source paths")

    # Track source directories for cleanup
    source_dirs = set()
    for src in source_paths:
        if src.is_dir():
            source_dirs.add(src)
        else:
            source_dirs.add(src.parent)

    # Phase 1b: Archive handling
    temp_dir = tempfile.mkdtemp(prefix="megaqueue_")
    try:
        extracted_files, non_archive_files = _extract_archives(all_files, temp_dir)
        files_to_route = extracted_files + non_archive_files

        if not files_to_route:
            raise FileNotFoundError("No files to organize after archive extraction")

        # Phase 2: Routing — move each file to its Plex destination
        final_paths = []
        for file_path in files_to_route:
            if download.media_type == "movie":
                final_paths.append(_route_movie(file_path, download))
            else:
                final_paths.append(_route_tv(file_path, download))

    finally:
        # Always clean up temp extraction directory
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Phase 3: Cleanup — delete source files/directories
    # Only clean up if all files were successfully moved (we got here without exception)
    download_dir = Path(config.MEGABASTERD_DOWNLOAD_DIR)
    for src in source_paths:
        try:
            if src.is_dir() and src.exists():
                shutil.rmtree(str(src), ignore_errors=True)
            elif src.is_file() and src.exists():
                src.unlink()
        except Exception as e:
            log.warning("Failed to clean up source %s: %s", src, e)

    # Also clean up any parent directories that are now empty and inside the download dir
    for d in source_dirs:
        try:
            if d.exists() and d != download_dir and not any(d.iterdir()):
                d.rmdir()
        except Exception:
            pass

    return final_paths
