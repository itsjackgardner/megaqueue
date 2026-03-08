import logging
import re
import shutil
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


def _extract_archives(files, extract_dir):
    """Extract any archives among the files. Returns list of extracted file paths."""
    archives = [f for f in files if _is_archive(f)]
    if not archives:
        return files

    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        import patoolib
        # Extract the first archive (for split archives, patool handles .001/.rar chains)
        patoolib.extract_archive(str(archives[0]), outdir=str(extract_dir))
    except ImportError:
        log.warning("patool not available, trying 7z subprocess")
        import subprocess
        subprocess.run(
            ["7z", "x", str(archives[0]), f"-o{extract_dir}", "-y"],
            check=True,
            capture_output=True,
        )

    # Return all non-archive files from the extraction directory
    extracted = [f for f in extract_dir.rglob("*") if f.is_file() and not _is_archive(f)]
    # Also include any original non-archive files
    non_archive_originals = [f for f in files if not _is_archive(f)]
    return extracted + non_archive_originals


def _move_file(src, dest_dir, filename):
    """Move a file to dest_dir, creating directories as needed. Returns destination path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    shutil.move(str(src), str(dest))
    log.info("Moved %s -> %s", src, dest)
    return str(dest)


def organize_download(download):
    """Organize downloaded files into Plex library folders.

    Returns list of final file paths.
    """
    # Find megabasterd's download directory for this download
    # Megabasterd downloads to its configured default path; we look for files there
    # The download's file_paths should be populated after megabasterd reports completion
    # For now, we use megabasterd's download path from config
    mb_download_path = Path(config.MEGABASTERD_API_URL).parent  # This won't work — need actual path

    # The organizer needs to know WHERE megabasterd put the files.
    # Since megabasterd's /status API returns the download path, the worker should pass it.
    # For now, we'll work with whatever file_paths are set on the download.

    source_files = [Path(p) for p in download.file_paths if Path(p).exists()]
    if not source_files:
        raise FileNotFoundError("No downloaded files found to organize")

    # Extract archives if present
    extract_dir = source_files[0].parent / "_extracted"
    files_to_organize = _extract_archives(source_files, extract_dir)

    final_paths = []

    for file_path in files_to_organize:
        if download.media_type == "movie":
            final_paths.append(_organize_movie(file_path, download))
        else:
            final_paths.append(_organize_tv(file_path, download))

    # Clean up temp/extraction directories
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)

    # Clean up original archive files
    for f in source_files:
        if _is_archive(f) and f.exists():
            f.unlink()

    return final_paths


def _organize_movie(file_path, download):
    """Move a movie file to PLEX_MOVIES_DIR/<Title> (<Year>)/"""
    if download.year:
        folder_name = f"{download.title} ({download.year})"
    else:
        folder_name = download.title

    dest_dir = Path(config.PLEX_MOVIES_DIR) / folder_name
    return _move_file(file_path, dest_dir, file_path.name)


def _organize_tv(file_path, download):
    """Move a TV file to PLEX_TV_DIR/<Title>/Season XX/"""
    season = _detect_season(file_path.name)
    base_dir = Path(config.PLEX_TV_DIR) / download.title

    if season is not None:
        dest_dir = base_dir / f"Season {season:02d}"
    else:
        dest_dir = base_dir

    return _move_file(file_path, dest_dir, file_path.name)
