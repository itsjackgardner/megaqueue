"""Download lifecycle: status derivation, source-path resolution, post-processing orchestration."""

import logging
from pathlib import Path

from megaqueue import config, organiser
from megaqueue.enums import DownloadStatus, FileStatus, MetadataConfidence, MetadataSource
from megaqueue.models import db_session
from megaqueue.notifications import notify_completion, notify_failure, notify_needs_review

log = logging.getLogger(__name__)


def derive_download_status(download):
    """Compute the overall download status from leaf file statuses and metadata confidence.

    Order of precedence:
      1. All files failed                              -> FAILED
      2. Low confidence with named files (not user-set) -> NEEDS_REVIEW
         (fires *as soon as* filenames are known — not gated on completion)
      3. All files finished                            -> PROCESSING (organiser runs)
      4. Any file downloading or finished              -> DOWNLOADING
      5. Otherwise                                     -> QUEUED
    """
    leaves = download.leaf_files
    statuses = [f.status for f in leaves]
    if not statuses:
        return download.status

    if all(s == FileStatus.FAILED for s in statuses):
        return DownloadStatus.FAILED

    has_named = any(f.name for f in leaves)
    low_confidence = download.metadata_confidence == MetadataConfidence.LOW
    not_user_set = download.metadata_source != MetadataSource.USER
    if has_named and low_confidence and not_user_set:
        return DownloadStatus.NEEDS_REVIEW

    if all(s == FileStatus.FINISHED for s in statuses):
        return DownloadStatus.PROCESSING
    if any(s in (FileStatus.DOWNLOADING, FileStatus.FINISHED) for s in statuses):
        return DownloadStatus.DOWNLOADING
    return DownloadStatus.QUEUED


def resolve_source_paths(download):
    """Resolve source file paths from DownloadFile.name fields for post-processing.

    Returns (source_paths, pre_extracted) where pre_extracted[i] is True
    if the path is a pre-extracted directory rather than the original file.
    """
    from megaqueue.organiser import ARCHIVE_EXTENSIONS, _has_media_files

    download_dir = Path(config.MEGABASTERD_DOWNLOAD_DIR)
    source_paths = []
    pre_extracted = []

    for df in download.leaf_files:
        if not df.name:
            raise ValueError(
                f"Could not determine download file path: DownloadFile name not set "
                f"for id={df.id}"
            )
        file_path = download_dir / df.name
        if file_path.exists():
            source_paths.append(file_path)
            pre_extracted.append(False)
        elif file_path.suffix.lower() in ARCHIVE_EXTENSIONS:
            stem_dir = download_dir / file_path.stem
            if stem_dir.is_dir() and _has_media_files(stem_dir):
                log.info(
                    "Archive '%s' not found, using pre-extracted directory '%s'",
                    df.name, stem_dir,
                )
                source_paths.append(stem_dir)
                pre_extracted.append(True)
            elif stem_dir.is_dir():
                raise FileNotFoundError(
                    f"Archive '{df.name}' not found and directory '{stem_dir}' "
                    f"contains no media files"
                )
            else:
                raise FileNotFoundError(
                    f"Source file not found: {file_path} "
                    f"(also checked for pre-extracted directory '{stem_dir}')"
                )
        else:
            raise FileNotFoundError(f"Source file not found: {file_path}")

    if not source_paths:
        raise FileNotFoundError("No source file paths resolved")

    return source_paths, pre_extracted


def _stop_megabasterd_entries(download, client):
    """Try to clear this download from megabasterd so it releases file handles.

    First tries stopping by each DownloadFile URL. If any return 404 (URL
    mismatch — common with folder downloads), falls back to matching by
    filename against megabasterd's /status response and stopping those.
    """
    stopped_urls = set()
    had_miss = False

    for df in download.files:
        if df.url and df.url not in stopped_urls:
            try:
                result = client.stop(df.url, delete=False)
                stopped_urls.add(df.url)
                if result is None:
                    had_miss = True
            except Exception:
                had_miss = True

    if not had_miss:
        return

    leaf_names = {df.name for df in download.leaf_files if df.name}
    if not leaf_names:
        return

    try:
        status = client.status()
        mb_downloads = status.get("downloads", []) if isinstance(status, dict) else []
        for mb_dl in mb_downloads:
            mb_name = mb_dl.get("name", "")
            mb_url = mb_dl.get("url", "")
            if mb_name in leaf_names and mb_url not in stopped_urls:
                try:
                    client.stop(mb_url, delete=False)
                    stopped_urls.add(mb_url)
                    log.info("Stopped megabasterd entry by name match: '%s'", mb_name)
                except Exception:
                    pass
    except Exception:
        log.debug("Could not fetch megabasterd status for name-based stop fallback")


def post_process(download, client):
    """Organize files, send notification, and clear from megabasterd."""
    log.info("Post-processing started for '%s'", download.title)

    _stop_megabasterd_entries(download, client)

    try:
        source_paths, pre_extracted = resolve_source_paths(download)
        final_paths = organiser.organize_download(download, source_paths, pre_extracted)
        for df, fp in zip(download.leaf_files, final_paths):
            if fp:
                df.file_path = fp
        download.status = DownloadStatus.COMPLETE
        db_session.commit()
        notify_completion(download)
    except Exception as e:
        log.error("Post-processing failed for '%s': %s", download.title, e)
        download.status = DownloadStatus.FAILED
        download.error_message = f"File organization failed: {e}"
        db_session.commit()
        notify_failure(download)
