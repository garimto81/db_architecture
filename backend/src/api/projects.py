"""
Projects API Router

Endpoints for Project operations.
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.services.project_service import ProjectService
from src.schemas.project import (
    ProjectResponse,
    ProjectListResponse,
    ProjectStatsResponse,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
def list_projects(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
) -> ProjectListResponse:
    """
    Get all projects.

    - **is_active**: Optional filter for active/inactive projects
    """
    service = ProjectService(db)
    return service.list_projects(is_active=is_active)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    """
    Get a single project by ID.
    """
    service = ProjectService(db)
    project = service.get_project(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}/stats", response_model=ProjectStatsResponse)
def get_project_stats(
    project_id: UUID,
    db: Session = Depends(get_db),
) -> ProjectStatsResponse:
    """
    Get statistics for a project.

    Returns counts of seasons, events, episodes, and video files,
    along with total duration and storage size.
    """
    service = ProjectService(db)
    stats = service.get_project_stats(project_id)

    if not stats:
        raise HTTPException(status_code=404, detail="Project not found")

    return stats
