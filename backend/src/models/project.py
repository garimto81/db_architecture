"""
Project Model

Top-level entity representing poker series (WSOP, HCL, etc.)
"""
import uuid
from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.orm import relationship

from src.database import Base
from src.models.types import GUID, TimestampMixin


class Project(Base, TimestampMixin):
    """
    Project (Poker Series)

    Examples: WSOP, HCL, GGMILLIONS, MPP, PAD, GOG, OTHER
    """
    __tablename__ = "projects"
    __table_args__ = {"schema": "pokervod"}

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    nas_base_path = Column(String(500))
    filename_pattern = Column(String(500))
    is_active = Column(Boolean, default=True)

    # Relationships
    seasons = relationship(
        "Season",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __repr__(self):
        return f"<Project(code={self.code}, name={self.name})>"
