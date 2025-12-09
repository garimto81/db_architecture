"""
Season Schemas

Pydantic models for Season endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from uuid import UUID

from src.schemas.common import ProjectCode, SeasonStatus


class SeasonBase(BaseModel):
    """Base season schema"""
    year: int = Field(..., ge=1973, le=2030, description="Season year")
    name: str = Field(..., max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    sub_category: Optional[str] = Field(None, max_length=50)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = "active"


class SeasonResponse(SeasonBase):
    """Season response schema"""
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SeasonWithProjectResponse(SeasonResponse):
    """Season response with project info"""
    project_code: str
    project_name: str


class SeasonFilter(BaseModel):
    """Season filter parameters"""
    project_code: Optional[ProjectCode] = Field(None, description="Filter by project code")
    year: Optional[int] = Field(None, ge=1973, le=2030, description="Filter by year")
    sub_category: Optional[str] = Field(None, description="Filter by sub_category (WSOP only)")
    status: Optional[SeasonStatus] = Field(None, description="Filter by status")
