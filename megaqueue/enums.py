from enum import StrEnum


class DownloadStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    NEEDS_REVIEW = "needs_review"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    FINISHED = "finished"
    FAILED = "failed"


class MediaType(StrEnum):
    MOVIE = "movie"
    TV = "tv"


class MetadataConfidence(StrEnum):
    HIGH = "high"
    LOW = "low"


class MetadataSource(StrEnum):
    GUESSIT = "guessit"
    USER = "user"
