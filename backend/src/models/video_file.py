"""
VideoFile Model

Represents physical video file metadata
"""
import uuid
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from src.database import Base
from src.models.types import GUID, TimestampMixin


class VideoFile(Base, TimestampMixin):
    """
    Video File Metadata

    Stores information about physical video files on NAS.
    """
    __tablename__ = "video_files"
    __table_args__ = {"schema": "pokervod"}

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    episode_id = Column(
        GUID,
        ForeignKey("pokervod.episodes.id", ondelete="SET NULL"),
        nullable=True
    )
    file_path = Column(String(1000), unique=True, nullable=False)
    file_name = Column(String(500), nullable=False)
    file_size_bytes = Column(BigInteger)
    file_format = Column(String(20))    # mp4, mov, mxf, avi, mkv
    resolution = Column(String(20))
    video_codec = Column(String(50))
    audio_codec = Column(String(50))
    bitrate_kbps = Column(Integer)
    duration_seconds = Column(Integer)
    version_type = Column(String(20))   # clean, mastered, stream, subclip, etc.
    is_original = Column(Boolean, default=False)
    checksum = Column(String(64))
    file_mtime = Column(DateTime(timezone=True))
    scan_status = Column(String(20), default="pending")

    # Filtering
    is_hidden = Column(Boolean, default=False)       # Hidden from catalog
    hidden_reason = Column(String(50))               # macos_meta, non_mp4, duplicate

    # Display (legacy)
    display_title = Column(String(500))              # Auto-generated readable title

    # Catalog System
    content_type = Column(String(20))                # full_episode, hand_clip, highlight, etc.
    catalog_title = Column(String(300))              # Group title: "WSOP 2024 Main Event"
    episode_title = Column(String(300))              # Item title: "Day 1A" or "Ding vs Boianovsky"
    ai_description = Column(Text)                    # AI-generated description [추후 구현]
    is_catalog_item = Column(Boolean, default=False) # Representative file for catalog display

    # Relationships
    episode = relationship("Episode", back_populates="video_files")

    def __repr__(self):
        return f"<VideoFile(file_name={self.file_name}, version_type={self.version_type})>"
