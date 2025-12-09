"""
Catalog Service

Business logic for flat-list catalog operations.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session, joinedload

from src.models.video_file import VideoFile
from src.models.episode import Episode
from src.models.event import Event
from src.models.season import Season
from src.models.project import Project


class CatalogService:
    """
    Catalog service for flat-list video browsing.

    Provides Netflix-style browsing where each video file is an independent
    item with its context (project, year, event) embedded.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_catalog_items(
        self,
        page: int = 1,
        page_size: int = 20,
        project_code: Optional[str] = None,
        year: Optional[int] = None,
        search: Optional[str] = None,
        include_hidden: bool = False,
        version_type: Optional[str] = None,
        file_format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get paginated catalog items with filters.

        Returns:
            Dictionary with items, total, page, page_size, total_pages
        """
        # Build base query with joins for context
        query = (
            select(
                VideoFile,
                Project.code.label('project_code'),
                Project.name.label('project_name'),
                Season.year.label('season_year'),
                Event.name.label('event_name'),
                Episode.title.label('episode_title'),
            )
            .outerjoin(Episode, VideoFile.episode_id == Episode.id)
            .outerjoin(Event, Episode.event_id == Event.id)
            .outerjoin(Season, Event.season_id == Season.id)
            .outerjoin(Project, Season.project_id == Project.id)
        )

        # Apply filters
        conditions = []

        if not include_hidden:
            conditions.append(or_(
                VideoFile.is_hidden.is_(False),
                VideoFile.is_hidden.is_(None)
            ))

        if project_code:
            conditions.append(Project.code == project_code.upper())

        if year:
            # Filter by season year
            conditions.append(Season.year == year)

        if search:
            search_pattern = f"%{search}%"
            conditions.append(or_(
                VideoFile.display_title.ilike(search_pattern),
                VideoFile.file_name.ilike(search_pattern)
            ))

        if version_type:
            conditions.append(VideoFile.version_type == version_type)

        if file_format:
            conditions.append(VideoFile.file_format == file_format.lower())

        if conditions:
            query = query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.execute(count_query).scalar() or 0

        # Apply ordering and pagination
        query = (
            query
            .order_by(
                Project.code.asc().nulls_last(),
                Season.year.desc().nulls_last(),
                VideoFile.display_title.asc().nulls_last(),
                VideoFile.file_name.asc()
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        # Execute and map results
        results = self.db.execute(query).all()

        items = []
        for row in results:
            video_file = row[0]

            items.append({
                "id": video_file.id,
                "display_title": video_file.display_title,
                "file_name": video_file.file_name,
                "file_path": video_file.file_path,
                "duration_seconds": video_file.duration_seconds,
                "file_size_bytes": video_file.file_size_bytes,
                "file_format": video_file.file_format,
                "resolution": video_file.resolution,
                "version_type": video_file.version_type,
                "project_code": row.project_code,
                "project_name": row.project_name,
                "year": row.season_year,
                "event_name": row.event_name,
                "episode_title": row.episode_title,
                "is_hidden": video_file.is_hidden or False,
                "hidden_reason": video_file.hidden_reason,
                "scan_status": video_file.scan_status or "pending",
                "created_at": video_file.created_at,
                "updated_at": video_file.updated_at,
                "file_mtime": video_file.file_mtime,
            })

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_catalog_item(self, video_id: UUID) -> Optional[Dict[str, Any]]:
        """Get single catalog item by ID."""
        query = (
            select(
                VideoFile,
                Project.code.label('project_code'),
                Project.name.label('project_name'),
                Season.year.label('season_year'),
                Event.name.label('event_name'),
                Episode.title.label('episode_title'),
            )
            .outerjoin(Episode, VideoFile.episode_id == Episode.id)
            .outerjoin(Event, Episode.event_id == Event.id)
            .outerjoin(Season, Event.season_id == Season.id)
            .outerjoin(Project, Season.project_id == Project.id)
            .where(VideoFile.id == video_id)
        )

        row = self.db.execute(query).first()
        if not row:
            return None

        video_file = row[0]

        return {
            "id": video_file.id,
            "display_title": video_file.display_title,
            "file_name": video_file.file_name,
            "file_path": video_file.file_path,
            "duration_seconds": video_file.duration_seconds,
            "file_size_bytes": video_file.file_size_bytes,
            "file_format": video_file.file_format,
            "resolution": video_file.resolution,
            "version_type": video_file.version_type,
            "project_code": row.project_code,
            "project_name": row.project_name,
            "year": row.season_year,
            "event_name": row.event_name,
            "episode_title": row.episode_title,
            "is_hidden": video_file.is_hidden or False,
            "hidden_reason": video_file.hidden_reason,
            "scan_status": video_file.scan_status or "pending",
            "created_at": video_file.created_at,
            "updated_at": video_file.updated_at,
            "file_mtime": video_file.file_mtime,
        }

    def get_catalog_stats(self, include_hidden: bool = False) -> Dict[str, Any]:
        """
        Get catalog statistics.

        Returns counts by project, year, format and totals.
        """
        # Base condition for visibility
        if include_hidden:
            visibility_condition = True
        else:
            visibility_condition = or_(
                VideoFile.is_hidden.is_(False),
                VideoFile.is_hidden.is_(None)
            )

        # Total counts
        total_files = self.db.execute(
            select(func.count(VideoFile.id))
        ).scalar() or 0

        visible_files = self.db.execute(
            select(func.count(VideoFile.id))
            .where(visibility_condition)
        ).scalar() or 0

        hidden_files = self.db.execute(
            select(func.count(VideoFile.id))
            .where(VideoFile.is_hidden.is_(True))
        ).scalar() or 0

        # By project
        by_project_query = (
            select(Project.code, func.count(VideoFile.id))
            .select_from(VideoFile)
            .outerjoin(Episode, VideoFile.episode_id == Episode.id)
            .outerjoin(Event, Episode.event_id == Event.id)
            .outerjoin(Season, Event.season_id == Season.id)
            .outerjoin(Project, Season.project_id == Project.id)
            .where(visibility_condition)
            .group_by(Project.code)
        )
        by_project = dict(self.db.execute(by_project_query).all())

        # By year (from season)
        by_year_query = (
            select(Season.year, func.count(VideoFile.id))
            .select_from(VideoFile)
            .outerjoin(Episode, VideoFile.episode_id == Episode.id)
            .outerjoin(Event, Episode.event_id == Event.id)
            .outerjoin(Season, Event.season_id == Season.id)
            .where(visibility_condition)
            .where(Season.year.isnot(None))
            .group_by(Season.year)
            .order_by(Season.year.desc())
        )
        by_year = {str(k): v for k, v in self.db.execute(by_year_query).all()}

        # By format
        by_format_query = (
            select(VideoFile.file_format, func.count(VideoFile.id))
            .where(visibility_condition)
            .where(VideoFile.file_format.isnot(None))
            .group_by(VideoFile.file_format)
        )
        by_format = dict(self.db.execute(by_format_query).all())

        # Total duration and size
        totals = self.db.execute(
            select(
                func.sum(VideoFile.duration_seconds),
                func.sum(VideoFile.file_size_bytes)
            )
            .where(visibility_condition)
        ).first()

        total_duration_hours = None
        total_size_gb = None

        if totals:
            if totals[0]:
                total_duration_hours = round(totals[0] / 3600, 2)
            if totals[1]:
                total_size_gb = round(totals[1] / (1024 ** 3), 2)

        return {
            "total_files": total_files,
            "visible_files": visible_files,
            "hidden_files": hidden_files,
            "by_project": by_project,
            "by_year": by_year,
            "by_format": by_format,
            "total_duration_hours": total_duration_hours,
            "total_size_gb": total_size_gb,
        }

    def get_filter_options(self) -> Dict[str, List[Any]]:
        """
        Get available filter options for UI dropdowns.

        Returns distinct values for project_codes, years, formats, version_types.
        """
        # Projects with video files
        projects = self.db.execute(
            select(Project.code, Project.name)
            .select_from(VideoFile)
            .join(Episode, VideoFile.episode_id == Episode.id)
            .join(Event, Episode.event_id == Event.id)
            .join(Season, Event.season_id == Season.id)
            .join(Project, Season.project_id == Project.id)
            .distinct()
            .order_by(Project.code)
        ).all()

        # Years
        years = self.db.execute(
            select(Season.year)
            .select_from(VideoFile)
            .join(Episode, VideoFile.episode_id == Episode.id)
            .join(Event, Episode.event_id == Event.id)
            .join(Season, Event.season_id == Season.id)
            .where(Season.year.isnot(None))
            .distinct()
            .order_by(Season.year.desc())
        ).scalars().all()

        # Formats
        formats = self.db.execute(
            select(VideoFile.file_format)
            .where(VideoFile.file_format.isnot(None))
            .distinct()
            .order_by(VideoFile.file_format)
        ).scalars().all()

        # Version types
        version_types = self.db.execute(
            select(VideoFile.version_type)
            .where(VideoFile.version_type.isnot(None))
            .distinct()
            .order_by(VideoFile.version_type)
        ).scalars().all()

        return {
            "projects": [{"code": p[0], "name": p[1]} for p in projects],
            "years": [y for y in years if y],
            "formats": [f for f in formats if f],
            "version_types": [v for v in version_types if v],
        }

    def get_catalog_groups(
        self,
        page: int = 1,
        page_size: int = 20,
        project_code: Optional[str] = None,
        content_type: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get catalog groups (grouped by catalog_title).

        Returns groups with episode counts, not individual files.
        """
        # Build base query for groups
        query = (
            select(
                VideoFile.catalog_title,
                VideoFile.content_type,
                func.count(VideoFile.id).label('episode_count'),
                func.sum(VideoFile.file_size_bytes).label('total_size'),
            )
            .where(VideoFile.is_hidden == False)
            .where(VideoFile.is_catalog_item == True)
            .where(VideoFile.catalog_title.isnot(None))
        )

        # Add project filter via join
        if project_code:
            query = (
                query
                .outerjoin(Episode, VideoFile.episode_id == Episode.id)
                .outerjoin(Event, Episode.event_id == Event.id)
                .outerjoin(Season, Event.season_id == Season.id)
                .outerjoin(Project, Season.project_id == Project.id)
                .where(Project.code == project_code.upper())
            )

        if content_type:
            query = query.where(VideoFile.content_type == content_type)

        # Group by catalog_title and content_type
        query = query.group_by(VideoFile.catalog_title, VideoFile.content_type)

        # Get total count
        count_subquery = query.subquery()
        total = self.db.execute(
            select(func.count()).select_from(count_subquery)
        ).scalar() or 0

        # Apply ordering and pagination
        query = (
            query
            .order_by(VideoFile.catalog_title.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        results = self.db.execute(query).all()

        groups = []
        for row in results:
            groups.append({
                "catalog_title": row.catalog_title,
                "content_type": row.content_type,
                "episode_count": row.episode_count,
                "total_size_gb": round(row.total_size / (1024 ** 3), 2) if row.total_size else 0,
            })

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return {
            "groups": groups,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_catalog_group_episodes(
        self,
        catalog_title: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get episodes within a catalog group.
        """
        # Build query for episodes in this group
        query = (
            select(VideoFile)
            .where(VideoFile.is_hidden == False)
            .where(VideoFile.is_catalog_item == True)
            .where(VideoFile.catalog_title == catalog_title)
        )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.execute(count_query).scalar() or 0

        # Get content_type for this group
        content_type = self.db.execute(
            select(VideoFile.content_type)
            .where(VideoFile.catalog_title == catalog_title)
            .limit(1)
        ).scalar()

        # Apply ordering and pagination
        query = (
            query
            .order_by(VideoFile.episode_title.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        results = self.db.execute(query).scalars().all()

        episodes = []
        for vf in results:
            episodes.append({
                "id": vf.id,
                "episode_title": vf.episode_title,
                "ai_description": vf.ai_description or "[추후 구현]",
                "version_type": vf.version_type,
                "file_size_gb": round(vf.file_size_bytes / (1024 ** 3), 2) if vf.file_size_bytes else 0,
                "duration_minutes": round(vf.duration_seconds / 60, 1) if vf.duration_seconds else None,
                "file_name": vf.file_name,
                "file_path": vf.file_path,
            })

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return {
            "catalog_title": catalog_title,
            "content_type": content_type,
            "episodes": episodes,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
