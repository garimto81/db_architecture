"""
Event Service

Business logic for Event operations.
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import math

from src.models import Project, Season, Event, Episode, VideoFile
from src.schemas.event import (
    EventResponse,
    EventDetailResponse,
    EventFilter,
)
from src.schemas.episode import EpisodeResponse, VideoFileResponse
from src.schemas.common import PaginatedResponse, PaginationParams


class EventService:
    """Service class for Event operations"""

    def __init__(self, db: Session):
        self.db = db

    def list_events(
        self,
        filters: EventFilter,
        pagination: PaginationParams,
    ) -> PaginatedResponse[EventDetailResponse]:
        """Get events with filtering and pagination"""
        # Base query with joins
        query = (
            select(Event, Season, Project)
            .join(Season, Event.season_id == Season.id)
            .join(Project, Season.project_id == Project.id)
            .where(Event.deleted_at.is_(None))
        )

        # Apply filters
        if filters.season_id:
            query = query.where(Event.season_id == filters.season_id)

        if filters.event_type:
            query = query.where(Event.event_type == filters.event_type.value)

        if filters.game_type:
            query = query.where(Event.game_type == filters.game_type.value)

        if filters.min_buy_in is not None:
            query = query.where(Event.buy_in >= filters.min_buy_in)

        if filters.max_buy_in is not None:
            query = query.where(Event.buy_in <= filters.max_buy_in)

        if filters.status:
            query = query.where(Event.status == filters.status)

        # Get total count (simplified)
        count_result = self.db.execute(
            select(func.count(Event.id)).where(Event.deleted_at.is_(None))
        )
        total = count_result.scalar() or 0

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = query.order_by(Event.start_date.desc().nullslast(), Event.name).offset(
            offset
        ).limit(pagination.page_size)

        result = self.db.execute(query)
        rows = result.all()

        items = []
        for event, season, project in rows:
            # Count episodes for this event
            episode_count = self.db.execute(
                select(func.count(Episode.id)).where(
                    Episode.event_id == event.id, Episode.deleted_at.is_(None)
                )
            ).scalar() or 0

            item = EventDetailResponse(
                id=event.id,
                season_id=event.season_id,
                event_number=event.event_number,
                name=event.name,
                name_short=event.name_short,
                event_type=event.event_type,
                game_type=event.game_type,
                buy_in=event.buy_in,
                gtd_amount=event.gtd_amount,
                venue=event.venue,
                entry_count=event.entry_count,
                prize_pool=event.prize_pool,
                start_date=event.start_date,
                end_date=event.end_date,
                total_days=event.total_days,
                status=event.status,
                created_at=event.created_at,
                updated_at=event.updated_at,
                season_name=season.name,
                season_year=season.year,
                project_code=project.code,
                project_name=project.name,
                episode_count=episode_count,
            )
            items.append(item)

        return PaginatedResponse(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=math.ceil(total / pagination.page_size) if total > 0 else 0,
        )

    def get_event(self, event_id: UUID) -> Optional[EventDetailResponse]:
        """Get a single event by ID with full details"""
        query = (
            select(Event, Season, Project)
            .join(Season, Event.season_id == Season.id)
            .join(Project, Season.project_id == Project.id)
            .where(Event.id == event_id, Event.deleted_at.is_(None))
        )
        result = self.db.execute(query)
        row = result.one_or_none()

        if not row:
            return None

        event, season, project = row

        # Count episodes
        episode_count = self.db.execute(
            select(func.count(Episode.id)).where(
                Episode.event_id == event.id, Episode.deleted_at.is_(None)
            )
        ).scalar() or 0

        return EventDetailResponse(
            id=event.id,
            season_id=event.season_id,
            event_number=event.event_number,
            name=event.name,
            name_short=event.name_short,
            event_type=event.event_type,
            game_type=event.game_type,
            buy_in=event.buy_in,
            gtd_amount=event.gtd_amount,
            venue=event.venue,
            entry_count=event.entry_count,
            prize_pool=event.prize_pool,
            start_date=event.start_date,
            end_date=event.end_date,
            total_days=event.total_days,
            status=event.status,
            created_at=event.created_at,
            updated_at=event.updated_at,
            season_name=season.name,
            season_year=season.year,
            project_code=project.code,
            project_name=project.name,
            episode_count=episode_count,
        )

    def get_episodes_by_event(
        self, event_id: UUID, pagination: PaginationParams
    ) -> PaginatedResponse[EpisodeResponse]:
        """Get episodes for an event with pagination"""
        # Check event exists
        event = self.db.execute(
            select(Event).where(Event.id == event_id, Event.deleted_at.is_(None))
        ).scalar_one_or_none()

        if not event:
            return PaginatedResponse(
                items=[], total=0, page=1, page_size=pagination.page_size, total_pages=0
            )

        # Count total episodes
        total = self.db.execute(
            select(func.count(Episode.id)).where(
                Episode.event_id == event_id, Episode.deleted_at.is_(None)
            )
        ).scalar() or 0

        # Get episodes with pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = (
            select(Episode)
            .where(Episode.event_id == event_id, Episode.deleted_at.is_(None))
            .order_by(Episode.episode_number, Episode.day_number, Episode.part_number)
            .offset(offset)
            .limit(pagination.page_size)
        )

        episodes = self.db.execute(query).scalars().all()

        return PaginatedResponse(
            items=[EpisodeResponse.model_validate(e) for e in episodes],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=math.ceil(total / pagination.page_size) if total > 0 else 0,
        )

    def get_video_files_by_episode(
        self, episode_id: UUID
    ) -> List[VideoFileResponse]:
        """Get video files for an episode"""
        # Check episode exists
        episode = self.db.execute(
            select(Episode).where(Episode.id == episode_id, Episode.deleted_at.is_(None))
        ).scalar_one_or_none()

        if not episode:
            return []

        query = (
            select(VideoFile)
            .where(VideoFile.episode_id == episode_id, VideoFile.deleted_at.is_(None))
            .order_by(VideoFile.version_type, VideoFile.file_name)
        )

        video_files = self.db.execute(query).scalars().all()
        return [VideoFileResponse.model_validate(vf) for vf in video_files]
