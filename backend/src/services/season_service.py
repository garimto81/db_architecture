"""
Season Service

Business logic for Season operations.
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import Project, Season
from src.schemas.season import (
    SeasonResponse,
    SeasonWithProjectResponse,
    SeasonFilter,
)
from src.schemas.common import PaginatedResponse, PaginationParams
import math


class SeasonService:
    """Service class for Season operations"""

    def __init__(self, db: Session):
        self.db = db

    def list_seasons(
        self,
        filters: SeasonFilter,
        pagination: PaginationParams,
    ) -> PaginatedResponse[SeasonWithProjectResponse]:
        """Get seasons with filtering and pagination"""
        # Base query with join to project
        query = (
            select(Season, Project)
            .join(Project, Season.project_id == Project.id)
            .where(Season.deleted_at.is_(None))
        )

        # Apply filters
        if filters.project_code:
            query = query.where(Project.code == filters.project_code.value)

        if filters.year:
            query = query.where(Season.year == filters.year)

        if filters.sub_category:
            query = query.where(Season.sub_category == filters.sub_category)

        if filters.status:
            query = query.where(Season.status == filters.status.value)

        # Get total count
        count_query = select(Season.id).where(Season.deleted_at.is_(None))
        if filters.project_code:
            count_query = count_query.join(Project).where(
                Project.code == filters.project_code.value
            )
        if filters.year:
            count_query = count_query.where(Season.year == filters.year)
        if filters.sub_category:
            count_query = count_query.where(Season.sub_category == filters.sub_category)
        if filters.status:
            count_query = count_query.where(Season.status == filters.status.value)

        total = len(self.db.execute(count_query).scalars().all())

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = query.order_by(Season.year.desc(), Project.code).offset(offset).limit(
            pagination.page_size
        )

        result = self.db.execute(query)
        rows = result.all()

        items = []
        for season, project in rows:
            item = SeasonWithProjectResponse(
                id=season.id,
                project_id=season.project_id,
                year=season.year,
                name=season.name,
                location=season.location,
                sub_category=season.sub_category,
                start_date=season.start_date,
                end_date=season.end_date,
                status=season.status,
                created_at=season.created_at,
                updated_at=season.updated_at,
                project_code=project.code,
                project_name=project.name,
            )
            items.append(item)

        return PaginatedResponse(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=math.ceil(total / pagination.page_size) if total > 0 else 0,
        )

    def get_season(self, season_id: UUID) -> Optional[Season]:
        """Get a single season by ID"""
        query = select(Season).where(
            Season.id == season_id, Season.deleted_at.is_(None)
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_seasons_by_project(self, project_id: UUID) -> List[SeasonResponse]:
        """Get all seasons for a project"""
        query = (
            select(Season)
            .where(Season.project_id == project_id, Season.deleted_at.is_(None))
            .order_by(Season.year.desc())
        )
        result = self.db.execute(query)
        seasons = result.scalars().all()
        return [SeasonResponse.model_validate(s) for s in seasons]
