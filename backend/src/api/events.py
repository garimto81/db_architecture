"""
Events API Router

Endpoints for Event operations.
"""
from typing import Optional
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.services.event_service import EventService
from src.schemas.event import (
    EventDetailResponse,
    EventFilter,
)
from src.schemas.episode import EpisodeResponse
from src.schemas.common import (
    PaginatedResponse,
    PaginationParams,
    EventType,
    GameType,
)

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=PaginatedResponse[EventDetailResponse])
def list_events(
    season_id: Optional[UUID] = Query(None, description="Filter by season ID"),
    event_type: Optional[EventType] = Query(None, description="Filter by event type"),
    game_type: Optional[GameType] = Query(None, description="Filter by game type"),
    min_buy_in: Optional[Decimal] = Query(None, ge=0, description="Minimum buy-in"),
    max_buy_in: Optional[Decimal] = Query(None, ge=0, description="Maximum buy-in"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EventDetailResponse]:
    """
    Get events with optional filtering and pagination.

    - **season_id**: Filter by season
    - **event_type**: Filter by event type (bracelet, high_roller, etc.)
    - **game_type**: Filter by game type (NLHE, PLO, etc.)
    - **min_buy_in/max_buy_in**: Filter by buy-in range
    - **status**: Filter by status (upcoming, in_progress, completed)
    """
    service = EventService(db)

    filters = EventFilter(
        season_id=season_id,
        event_type=event_type,
        game_type=game_type,
        min_buy_in=min_buy_in,
        max_buy_in=max_buy_in,
        status=status,
    )

    pagination = PaginationParams(page=page, page_size=page_size)

    return service.list_events(filters=filters, pagination=pagination)


@router.get("/{event_id}", response_model=EventDetailResponse)
def get_event(
    event_id: UUID,
    db: Session = Depends(get_db),
) -> EventDetailResponse:
    """
    Get a single event by ID with full details.

    Includes parent season/project information and episode count.
    """
    service = EventService(db)
    event = service.get_event(event_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event


@router.get("/{event_id}/episodes", response_model=PaginatedResponse[EpisodeResponse])
def get_event_episodes(
    event_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EpisodeResponse]:
    """
    Get all episodes for an event.

    Episodes are ordered by episode_number, day_number, and part_number.
    """
    service = EventService(db)
    pagination = PaginationParams(page=page, page_size=page_size)

    return service.get_episodes_by_event(event_id, pagination)
