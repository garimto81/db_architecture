"""
Episode and VideoFile Schemas

Pydantic models for Episode and VideoFile endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from uuid import UUID


class EpisodeBase(BaseModel):
    """Base episode schema"""
    episode_number: Optional[int] = None
    day_number: Optional[int] = None
    part_number: Optional[int] = None
    title: Optional[str] = Field(None, max_length=500)
    episode_type: Optional[str] = None
    table_type: Optional[str] = None
    duration_seconds: Optional[int] = Field(None, gt=0)
    air_date: Optional[date] = None
    synopsis: Optional[str] = None


class EpisodeResponse(EpisodeBase):
    """Episode response schema"""
    id: UUID
    event_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoFileResponse(BaseModel):
    """Video file response schema"""
    id: UUID
    episode_id: Optional[UUID] = None
    file_path: str
    file_name: str
    file_size_bytes: Optional[int] = None
    file_format: Optional[str] = None
    resolution: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    bitrate_kbps: Optional[int] = None
    duration_seconds: Optional[int] = None
    version_type: Optional[str] = None
    is_original: bool = False
    scan_status: str = "pending"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
