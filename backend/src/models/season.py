"""
Season Model

Represents a yearly instance of a project (e.g., 2024 WSOP Las Vegas)
"""
import uuid
from sqlalchemy import Column, String, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base
from src.models.types import GUID, TimestampMixin


class Season(Base, TimestampMixin):
    """
    Season (Yearly Project Instance)

    Examples: 2024 WSOP Las Vegas, HCL Season 2024
    """
    __tablename__ = "seasons"
    __table_args__ = {"schema": "pokervod"}

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(
        GUID,
        ForeignKey("pokervod.projects.id", ondelete="CASCADE"),
        nullable=False
    )
    year = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    location = Column(String(200))
    sub_category = Column(String(50))  # WSOP only: BRACELET_LV, CIRCUIT, etc.
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String(20), default="active")

    # Relationships
    project = relationship("Project", back_populates="seasons")
    events = relationship(
        "Event",
        back_populates="season",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __repr__(self):
        return f"<Season(year={self.year}, name={self.name})>"
