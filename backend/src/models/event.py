"""
Event Model

Represents tournaments, cash games, or TV series episodes
"""
import uuid
from decimal import Decimal
from sqlalchemy import Column, String, Integer, Date, ForeignKey, Numeric
from sqlalchemy.orm import relationship

from src.database import Base
from src.models.types import GUID, TimestampMixin


class Event(Base, TimestampMixin):
    """
    Event (Tournament, Cash Game, TV Series)

    Examples: $10,000 NLHE Main Event, HCL Episode 15
    """
    __tablename__ = "events"
    __table_args__ = {"schema": "pokervod"}

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    season_id = Column(
        GUID,
        ForeignKey("pokervod.seasons.id", ondelete="CASCADE"),
        nullable=False
    )
    event_number = Column(Integer)
    name = Column(String(500), nullable=False)
    name_short = Column(String(100))
    event_type = Column(String(50))  # bracelet, circuit, cash_game, etc.
    game_type = Column(String(50))   # NLHE, PLO, Mixed, etc.
    buy_in = Column(Numeric(10, 2))
    gtd_amount = Column(Numeric(15, 2))
    venue = Column(String(200))
    entry_count = Column(Integer)
    prize_pool = Column(Numeric(15, 2))
    start_date = Column(Date)
    end_date = Column(Date)
    total_days = Column(Integer)
    status = Column(String(20), default="upcoming")

    # Relationships
    season = relationship("Season", back_populates="events")
    episodes = relationship(
        "Episode",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __repr__(self):
        return f"<Event(name={self.name}, event_type={self.event_type})>"
