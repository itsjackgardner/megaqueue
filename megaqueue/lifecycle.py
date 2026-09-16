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

    Returns (leaf_files, source_paths, pre_extracted) where:
    - leaf_files: the DownloadFile records that need organising (excludes already-organised)
    - source_paths: corresponding filesystem paths
    - pre_extracted[i]: True if path is a pre-extracted directory
    """
    from megaqueue.organiser import ARCHIVE_EXTENSIONS, _has_media_files

    download_dir = Path(config.DOWNLOAD_DIR)
    leaf_files = []
    source_paths = []
    pre_extracted = []

    for df in download.leaf_files:
        if df.file_path:
            continue
        if not df.name:
            raise ValueError(
                f"Could not determine download file path: DownloadFile name not set "
                f"for id={df.id}"
            )
        file_path = download_dir / df.name
        if file_path.exists():
            leaf_files.append(df)
            source_paths.append(file_path)
            pre_extracted.append(False)
        elif file_path.suffix.lower() in ARCHIVE_EXTENSIONS:
            stem_dir = download_dir / file_path.stem
            if stem_dir.is_dir() and _has_media_files(stem_dir):
                log.info(
                    "Archive '%s' not found, using pre-extracted directory '%s'",
                    df.name, stem_dir,
                )
                leaf_files.append(df)
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

    return leaf_files, source_paths, pre_extracted


def _cancel_active_downloads(download, manager):
    """Cancel active downloads and remove entries from the download manager."""
    for df in download.files:
        if df.url:
            try:
                manager.cancel(df.url)
                manager.remove(df.url)
            except Exception:
                pass


def post_process(download, manager):
    """Organize files, send notification, and clean up download entries."""
    log.info("Post-processing started for '%s'", download.title)

    _cancel_active_downloads(download, manager)

    try:
        pending_leaves, source_paths, pre_extracted = resolve_source_paths(download)
        final_paths = organiser.organize_download(download, source_paths, pre_extracted, pending_leaves)
        for df, fp in zip(pending_leaves, final_paths):
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
