"""
Episode Model

Represents individual video episodes within an event
"""
import uuid
from sqlalchemy import Column, String, Integer, Date, Text, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base
from src.models.types import GUID, TimestampMixin


class Episode(Base, TimestampMixin):
    """
    Episode (Individual Video Unit)

    Examples: Day 1 Part 1, Final Table, Highlight Reel
    """
    __tablename__ = "episodes"
    __table_args__ = {"schema": "pokervod"}

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    event_id = Column(
        GUID,
        ForeignKey("pokervod.events.id", ondelete="CASCADE"),
        nullable=False
    )
    episode_number = Column(Integer)
    day_number = Column(Integer)
    part_number = Column(Integer)
    title = Column(String(500))
    episode_type = Column(String(50))  # full, highlight, recap, interview, subclip
    table_type = Column(String(50))    # preliminary, day1, final_table, heads_up
    duration_seconds = Column(Integer)
    air_date = Column(Date)
    synopsis = Column(Text)

    # Relationships
    event = relationship("Event", back_populates="episodes")
    video_files = relationship(
        "VideoFile",
        back_populates="episode",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __repr__(self):
        return f"<Episode(title={self.title}, episode_type={self.episode_type})>"
