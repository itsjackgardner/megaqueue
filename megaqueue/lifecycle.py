"""Download lifecycle: status derivation, source-path resolution, post-processing orchestration."""

import logging
from pathlib import Path

from megaqueue import config, filebot_organizer
from megaqueue.enums import DownloadStatus, FileStatus, MetadataConfidence
from megaqueue.models import db_session
from megaqueue.notifications import notify_completion, notify_failure, notify_needs_review

log = logging.getLogger(__name__)


def derive_download_status(download):
    """Compute the overall download status from leaf file statuses and metadata confidence.

    All files finished + metadata_confidence == HIGH  -> PROCESSING (run organiser)
    All files finished + metadata_confidence == LOW   -> NEEDS_REVIEW (block, await user)
    All files failed                                  -> FAILED
    Any downloading/finished                          -> DOWNLOADING
    Otherwise                                         -> QUEUED
    """
    statuses = [f.status for f in download.leaf_files]
    if not statuses:
        return download.status

    if all(s == FileStatus.FINISHED for s in statuses):
        if download.metadata_confidence == MetadataConfidence.HIGH:
            return DownloadStatus.PROCESSING
        return DownloadStatus.NEEDS_REVIEW
    if all(s == FileStatus.FAILED for s in statuses):
        return DownloadStatus.FAILED
    if any(s in (FileStatus.DOWNLOADING, FileStatus.FINISHED) for s in statuses):
        return DownloadStatus.DOWNLOADING
    return DownloadStatus.QUEUED


def resolve_source_paths(download):
    """Resolve source file paths from DownloadFile.name fields for post-processing."""
    download_dir = Path(config.MEGABASTERD_DOWNLOAD_DIR)
    source_paths = []

    for df in download.leaf_files:
        if not df.name:
            raise ValueError(
                f"Could not determine download file path: DownloadFile name not set "
                f"for id={df.id}"
            )
        source_paths.append(download_dir / df.name)

    if not source_paths:
        raise FileNotFoundError("No source file paths resolved")

    return source_paths


def post_process(download, client):
    """Organize files, send notification, and clear from megabasterd."""
    try:
        source_paths = resolve_source_paths(download)
        final_paths = filebot_organizer.organize_download(download, source_paths)
        for df, fp in zip(download.leaf_files, final_paths):
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

    stopped_urls = set()
    for df in download.files:
        if df.url and df.url not in stopped_urls:
            try:
                client.stop(df.url, delete=False)
                stopped_urls.add(df.url)
            except Exception:
                pass
