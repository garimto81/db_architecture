"""
Pydantic Schemas

Export all schemas for easy importing.
"""
from src.schemas.common import (
    PaginationParams,
    PaginatedResponse,
    ProjectCode,
    EventType,
    GameType,
    SeasonStatus,
    EpisodeType,
    VersionType,
)
from src.schemas.project import (
    ProjectBase,
    ProjectResponse,
    ProjectListResponse,
    ProjectStatsResponse,
)
from src.schemas.season import (
    SeasonBase,
    SeasonResponse,
    SeasonFilter,
)
from src.schemas.event import (
    EventBase,
    EventResponse,
    EventDetailResponse,
    EventFilter,
)
from src.schemas.episode import (
    EpisodeBase,
    EpisodeResponse,
    VideoFileResponse,
)
from src.schemas.catalog import (
    CatalogItemResponse,
    CatalogListResponse,
    CatalogStatsResponse,
    CatalogFilterParams,
)

__all__ = [
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "ProjectCode",
    "EventType",
    "GameType",
    "SeasonStatus",
    "EpisodeType",
    "VersionType",
    # Project
    "ProjectBase",
    "ProjectResponse",
    "ProjectListResponse",
    "ProjectStatsResponse",
    # Season
    "SeasonBase",
    "SeasonResponse",
    "SeasonFilter",
    # Event
    "EventBase",
    "EventResponse",
    "EventDetailResponse",
    "EventFilter",
    # Episode
    "EpisodeBase",
    "EpisodeResponse",
    "VideoFileResponse",
    # Catalog
    "CatalogItemResponse",
    "CatalogListResponse",
    "CatalogStatsResponse",
    "CatalogFilterParams",
]
