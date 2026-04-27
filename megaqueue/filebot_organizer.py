import logging
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from megaqueue import config

log = logging.getLogger(__name__)

ARCHIVE_EXTENSIONS = {".rar", ".zip", ".7z", ".001"}

# Pattern for FileBot's rename output: [rename] From [/src] to [/dest]
_RENAME_LINE = re.compile(r"\[rename\] From \[(.+?)\] to \[(.+?)\]")


def _is_archive(path):
    return path.suffix.lower() in ARCHIVE_EXTENSIONS


def _parse_final_paths(stdout):
    """Extract destination paths from FileBot stdout rename lines."""
    paths = []
    for line in stdout.splitlines():
        m = _RENAME_LINE.search(line)
        if m:
            paths.append(m.group(2))
    return paths


def _fallback_scan(output_dir, since):
    """Return files in output_dir newer than the given datetime."""
    paths = []
    for p in Path(output_dir).rglob("*"):
        if p.is_file() and datetime.fromtimestamp(p.stat().st_mtime) > since:
            paths.append(str(p))
    return paths


def organize_download(download, source_paths):
    """Organize downloaded files into Plex library folders using FileBot.

    Args:
        download: Download model instance with title, year, media_type.
        source_paths: List of Path objects pointing to downloaded files.

    Returns list of final destination path strings (same order as non-archive
    source files, plus extracted files appended).
    """
    archives = [p for p in source_paths if _is_archive(p)]
    non_archives = [p for p in source_paths if not _is_archive(p)]

    plex_dir = config.PLEX_MOVIES_DIR if download.media_type == "movie" else config.PLEX_TV_DIR

    temp_dir = tempfile.mkdtemp(prefix="megaqueue_")
    try:
        # Step 1: Extract archives if present
        if archives:
            result = subprocess.run(
                [config.FILEBOT_BIN, "-extract"] + [str(a) for a in archives] + ["-output", temp_dir],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"FileBot archive extraction failed:\n{result.stderr}"
                )
            log.info("FileBot extracted archives to %s", temp_dir)

        # Build the list of inputs for the rename step:
        # extracted temp dir (if archives were present) + non-archive files
        rename_inputs = []
        if archives:
            rename_inputs.append(temp_dir)
        rename_inputs += [str(p) for p in non_archives]

        if not rename_inputs:
            raise FileNotFoundError("No files to organize after archive extraction")

        pre_invoke = datetime.now()

        # Step 2: Rename/move to Plex directory
        cmd = (
            [config.FILEBOT_BIN, "-rename"]
            + rename_inputs
            + [
                "-output", plex_dir,
                "-format", "{plex}",
                "-action", "move",
                "-q", download.title,
                "-non-strict",
            ]
        )
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "(no output)"
            raise RuntimeError(
                f"FileBot rename failed:\n{detail}"
            )

        log.info("FileBot rename stdout: %s", result.stdout)

        # Step 3: Parse final paths from stdout
        final_paths = _parse_final_paths(result.stdout)
        if not final_paths:
            log.warning("FileBot stdout parse yielded no paths, falling back to directory scan")
            final_paths = _fallback_scan(plex_dir, pre_invoke)

        return final_paths

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
