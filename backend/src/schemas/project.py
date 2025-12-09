"""
Project Schemas

Pydantic models for Project endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ProjectBase(BaseModel):
    """Base project schema"""
    code: str = Field(..., max_length=20, description="Project code (e.g., WSOP)")
    name: str = Field(..., max_length=200, description="Project name")
    description: Optional[str] = None
    nas_base_path: Optional[str] = Field(None, max_length=500)
    filename_pattern: Optional[str] = Field(None, max_length=500)
    is_active: bool = True


class ProjectResponse(ProjectBase):
    """Project response schema"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """List of projects response"""
    items: List[ProjectResponse]
    total: int


class ProjectStatsResponse(BaseModel):
    """Project statistics response"""
    project_id: UUID
    project_code: str
    project_name: str
    total_seasons: int = 0
    total_events: int = 0
    total_episodes: int = 0
    total_video_files: int = 0
    total_duration_hours: float = 0.0
    total_size_gb: float = 0.0
