"""
Episodes API Router

Endpoints for Episode and VideoFile operations.
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.services.event_service import EventService
from src.schemas.episode import VideoFileResponse

router = APIRouter(prefix="/api/episodes", tags=["episodes"])


@router.get("/{episode_id}/video-files", response_model=List[VideoFileResponse])
def get_episode_video_files(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> List[VideoFileResponse]:
    """
    Get all video files for an episode.

    Video files are ordered by version_type and file_name.
    Returns an empty list if the episode doesn't exist.
    """
    service = EventService(db)
    return service.get_video_files_by_episode(episode_id)
