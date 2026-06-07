import json
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker, relationship

from sqlalchemy import Boolean

from megaqueue import config, migrations
from megaqueue.enums import DownloadStatus, FileStatus, MediaType, MetadataConfidence, MetadataSource

Base = declarative_base()


def _enum_column(enum_cls, name, **kwargs):
    """Build a SQLAlchemy Enum column that stores the enum's string values (not member names)."""
    return Column(
        Enum(enum_cls, values_callable=lambda x: [e.value for e in x], name=name),
        **kwargs,
    )


class DownloadFile(Base):
    __tablename__ = "download_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    download_id = Column(Integer, ForeignKey("downloads.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("download_files.id", ondelete="CASCADE"), nullable=True)
    url = Column(String, nullable=False)
    name = Column(String, nullable=True)
    status = _enum_column(FileStatus, name="file_status", nullable=False, default=FileStatus.QUEUED)
    progress_bytes = Column(Integer, default=0)
    total_bytes = Column(Integer, default=0)
    speed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    file_path = Column(String, nullable=True)
    is_extra = Column(Boolean, nullable=False, default=False)

    children = relationship(
        "DownloadFile",
        foreign_keys="[DownloadFile.parent_id]",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "url": self.url,
            "name": self.name,
            "status": self.status,
            "progress_bytes": self.progress_bytes,
            "total_bytes": self.total_bytes,
            "speed": self.speed,
            "error_message": self.error_message,
            "file_path": self.file_path,
            "is_extra": self.is_extra,
        }


class Download(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    media_type = _enum_column(MediaType, name="media_type", nullable=True)
    status = _enum_column(DownloadStatus, name="status", nullable=False, default=DownloadStatus.QUEUED)
    downloading_since = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_confidence = _enum_column(
        MetadataConfidence, name="metadata_confidence",
        nullable=False, default=MetadataConfidence.LOW,
    )
    metadata_source = _enum_column(MetadataSource, name="metadata_source", nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    files = relationship("DownloadFile", backref="download", cascade="all, delete-orphan", lazy="joined")

    @property
    def top_level_files(self):
        """Files directly submitted by the user (parent_id is None)."""
        return [f for f in self.files if f.parent_id is None]

    @property
    def leaf_files(self):
        """Files representing actual download units (no children).

        For non-folder downloads: same as files.
        For expanded folder downloads: the per-file children, not the parent folder record.
        """
        return [f for f in self.files if not f.children]

    @property
    def links(self):
        return [f.url for f in self.top_level_files]

    @property
    def progress_bytes(self):
        return sum(f.progress_bytes for f in self.leaf_files)

    @property
    def total_bytes(self):
        return sum(f.total_bytes for f in self.leaf_files)

    @property
    def speed(self):
        return sum(f.speed for f in self.leaf_files)

    @property
    def file_paths(self):
        return [f.file_path for f in self.leaf_files if f.file_path]

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "year": self.year,
            "media_type": self.media_type,
            "status": self.status,
            "progress_bytes": self.progress_bytes,
            "total_bytes": self.total_bytes,
            "speed": self.speed,
            "downloading_since": self.downloading_since.isoformat() if self.downloading_since else None,
            "error_message": self.error_message,
            "metadata_confidence": self.metadata_confidence,
            "metadata_source": self.metadata_source,
            "file_paths": self.file_paths,
            "files": [f.to_dict() for f in self.leaf_files],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Database setup
engine = create_engine(config.DATABASE_URL, echo=False)
session_factory = sessionmaker(bind=engine)
db_session = scoped_session(session_factory)


def init_db():
    """Create all tables, enable WAL mode, and run schema migrations."""
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        migrations.run_all(conn)
