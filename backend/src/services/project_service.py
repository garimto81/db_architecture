"""
Project Service

Business logic for Project operations.
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import Project, Season, Event, Episode, VideoFile
from src.schemas.project import (
    ProjectResponse,
    ProjectListResponse,
    ProjectStatsResponse,
)


class ProjectService:
    """Service class for Project operations"""

    def __init__(self, db: Session):
        self.db = db

    def list_projects(self, is_active: Optional[bool] = None) -> ProjectListResponse:
        """Get all projects with optional active filter"""
        query = select(Project).where(Project.deleted_at.is_(None))

        if is_active is not None:
            query = query.where(Project.is_active == is_active)

        query = query.order_by(Project.code)
        result = self.db.execute(query)
        projects = result.scalars().all()

        return ProjectListResponse(
            items=[ProjectResponse.model_validate(p) for p in projects],
            total=len(projects),
        )

    def get_project(self, project_id: UUID) -> Optional[Project]:
        """Get a single project by ID"""
        query = select(Project).where(
            Project.id == project_id, Project.deleted_at.is_(None)
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_project_by_code(self, code: str) -> Optional[Project]:
        """Get a single project by code"""
        query = select(Project).where(
            Project.code == code, Project.deleted_at.is_(None)
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_project_stats(self, project_id: UUID) -> Optional[ProjectStatsResponse]:
        """Get statistics for a project"""
        project = self.get_project(project_id)
        if not project:
            return None

        # Count seasons
        season_count = self.db.execute(
            select(func.count(Season.id)).where(
                Season.project_id == project_id, Season.deleted_at.is_(None)
            )
        ).scalar()

        # Get season IDs for further queries
        season_ids = self.db.execute(
            select(Season.id).where(
                Season.project_id == project_id, Season.deleted_at.is_(None)
            )
        ).scalars().all()

        if not season_ids:
            return ProjectStatsResponse(
                project_id=project.id,
                project_code=project.code,
                project_name=project.name,
                total_seasons=0,
                total_events=0,
                total_episodes=0,
                total_video_files=0,
                total_duration_hours=0.0,
                total_size_gb=0.0,
            )

        # Count events
        event_count = self.db.execute(
            select(func.count(Event.id)).where(
                Event.season_id.in_(season_ids), Event.deleted_at.is_(None)
            )
        ).scalar()

        # Get event IDs
        event_ids = self.db.execute(
            select(Event.id).where(
                Event.season_id.in_(season_ids), Event.deleted_at.is_(None)
            )
        ).scalars().all()

        if not event_ids:
            return ProjectStatsResponse(
                project_id=project.id,
                project_code=project.code,
                project_name=project.name,
                total_seasons=season_count or 0,
                total_events=0,
                total_episodes=0,
                total_video_files=0,
                total_duration_hours=0.0,
                total_size_gb=0.0,
            )

        # Count episodes
        episode_count = self.db.execute(
            select(func.count(Episode.id)).where(
                Episode.event_id.in_(event_ids), Episode.deleted_at.is_(None)
            )
        ).scalar()

        # Get episode IDs
        episode_ids = self.db.execute(
            select(Episode.id).where(
                Episode.event_id.in_(event_ids), Episode.deleted_at.is_(None)
            )
        ).scalars().all()

        if not episode_ids:
            return ProjectStatsResponse(
                project_id=project.id,
                project_code=project.code,
                project_name=project.name,
                total_seasons=season_count or 0,
                total_events=event_count or 0,
                total_episodes=0,
                total_video_files=0,
                total_duration_hours=0.0,
                total_size_gb=0.0,
            )

        # Count video files and aggregate stats
        video_stats = self.db.execute(
            select(
                func.count(VideoFile.id),
                func.coalesce(func.sum(VideoFile.duration_seconds), 0),
                func.coalesce(func.sum(VideoFile.file_size_bytes), 0),
            ).where(
                VideoFile.episode_id.in_(episode_ids), VideoFile.deleted_at.is_(None)
            )
        ).one()

        video_count, total_duration, total_size = video_stats

        return ProjectStatsResponse(
            project_id=project.id,
            project_code=project.code,
            project_name=project.name,
            total_seasons=season_count or 0,
            total_events=event_count or 0,
            total_episodes=episode_count or 0,
            total_video_files=video_count or 0,
            total_duration_hours=round((total_duration or 0) / 3600, 2),
            total_size_gb=round((total_size or 0) / (1024**3), 2),
        )
