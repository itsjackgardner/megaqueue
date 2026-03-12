import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, Enum
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

import config

Base = declarative_base()


class Download(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    media_type = Column(Enum("movie", "tv", name="media_type"), nullable=False)
    _links = Column("links", Text, nullable=False)  # JSON list of mega.nz URLs
    status = Column(
        Enum("queued", "downloading", "processing", "complete", "failed", "cancelled", name="status"),
        nullable=False,
        default="queued",
    )
    progress_bytes = Column(Integer, default=0)
    total_bytes = Column(Integer, default=0)
    speed = Column(Integer, default=0)  # bytes per second
    downloading_since = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    _file_paths = Column("file_paths", Text, default="[]")  # JSON list of strings
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def links(self):
        return json.loads(self._links)

    @links.setter
    def links(self, value):
        self._links = json.dumps(value)

    @property
    def file_paths(self):
        return json.loads(self._file_paths)

    @file_paths.setter
    def file_paths(self, value):
        self._file_paths = json.dumps(value)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "year": self.year,
            "media_type": self.media_type,
            "links": self.links,
            "status": self.status,
            "progress_bytes": self.progress_bytes,
            "total_bytes": self.total_bytes,
            "speed": self.speed,
            "downloading_since": self.downloading_since.isoformat() if self.downloading_since else None,
            "error_message": self.error_message,
            "file_paths": self.file_paths,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Database setup
engine = create_engine(config.DATABASE_URL, echo=False)
session_factory = sessionmaker(bind=engine)
db_session = scoped_session(session_factory)


def init_db():
    """Create all tables and enable WAL mode."""
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        # Migrate: add downloading_since if missing
        result = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM pragma_table_info('downloads') WHERE name='downloading_since'"
        )
        if result.scalar() == 0:
            conn.exec_driver_sql("ALTER TABLE downloads ADD COLUMN downloading_since DATETIME")
        conn.commit()
