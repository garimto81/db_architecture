"""
Catalog Schemas

Pydantic models for flat-list catalog API (Netflix-style).
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from src.schemas.common import PaginatedResponse


class CatalogItemResponse(BaseModel):
    """
    Single catalog item (video file with context).

    This is the flat-list view - each video file is an independent item
    with its project/event context embedded.
    """
    # Video file info
    id: UUID
    display_title: Optional[str] = Field(None, description="Human-readable title")
    file_name: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Full NAS path")

    # Technical metadata
    duration_seconds: Optional[int] = None
    file_size_bytes: Optional[int] = None
    file_format: Optional[str] = None
    resolution: Optional[str] = None
    version_type: Optional[str] = None

    # Context (from joined tables)
    project_code: Optional[str] = Field(None, description="Project code (WSOP, HCL, etc.)")
    project_name: Optional[str] = Field(None, description="Project display name")
    year: Optional[int] = Field(None, description="Year from season or event")
    event_name: Optional[str] = Field(None, description="Event name")
    episode_title: Optional[str] = Field(None, description="Episode title if available")

    # Status
    is_hidden: bool = False
    hidden_reason: Optional[str] = None
    scan_status: str = "pending"

    # Timestamps
    created_at: datetime
    updated_at: datetime
    file_mtime: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CatalogListResponse(PaginatedResponse[CatalogItemResponse]):
    """Paginated catalog response"""
    pass


class CatalogStatsResponse(BaseModel):
    """Catalog statistics summary"""
    total_files: int = Field(..., description="Total video files")
    visible_files: int = Field(..., description="Files visible in catalog (not hidden)")
    hidden_files: int = Field(..., description="Hidden files count")

    by_project: dict = Field(default_factory=dict, description="File count by project")
    by_year: dict = Field(default_factory=dict, description="File count by year")
    by_format: dict = Field(default_factory=dict, description="File count by format")

    total_duration_hours: Optional[float] = Field(None, description="Total duration in hours")
    total_size_gb: Optional[float] = Field(None, description="Total size in GB")


class CatalogFilterParams(BaseModel):
    """Filter parameters for catalog queries"""
    project_code: Optional[str] = Field(None, description="Filter by project code")
    year: Optional[int] = Field(None, description="Filter by year")
    search: Optional[str] = Field(None, description="Search in display_title and file_name")
    include_hidden: bool = Field(False, description="Include hidden files")
    version_type: Optional[str] = Field(None, description="Filter by version type")
    file_format: Optional[str] = Field(None, description="Filter by file format (mp4, mov, etc.)")
