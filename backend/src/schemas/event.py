"""
Event Schemas

Pydantic models for Event endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from src.schemas.common import EventType, GameType


class EventBase(BaseModel):
    """Base event schema"""
    event_number: Optional[int] = None
    name: str = Field(..., max_length=500)
    name_short: Optional[str] = Field(None, max_length=100)
    event_type: Optional[str] = None
    game_type: Optional[str] = None
    buy_in: Optional[Decimal] = Field(None, ge=0)
    gtd_amount: Optional[Decimal] = Field(None, ge=0)
    venue: Optional[str] = Field(None, max_length=200)
    entry_count: Optional[int] = Field(None, ge=0)
    prize_pool: Optional[Decimal] = Field(None, ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_days: Optional[int] = Field(None, ge=1)
    status: str = "upcoming"


class EventResponse(EventBase):
    """Event response schema"""
    id: UUID
    season_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventDetailResponse(EventResponse):
    """Event detail with parent info"""
    season_name: str
    season_year: int
    project_code: str
    project_name: str
    episode_count: int = 0


class EventFilter(BaseModel):
    """Event filter parameters"""
    season_id: Optional[UUID] = Field(None, description="Filter by season ID")
    event_type: Optional[EventType] = Field(None, description="Filter by event type")
    game_type: Optional[GameType] = Field(None, description="Filter by game type")
    min_buy_in: Optional[Decimal] = Field(None, ge=0, description="Minimum buy-in")
    max_buy_in: Optional[Decimal] = Field(None, ge=0, description="Maximum buy-in")
    status: Optional[str] = Field(None, description="Filter by status")
