"""
Catalog API Router

Flat-list catalog endpoints for Netflix-style video browsing.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.services.catalog_service import CatalogService
from src.schemas.catalog import (
    CatalogItemResponse,
    CatalogListResponse,
    CatalogStatsResponse,
)


router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("", response_model=CatalogListResponse)
def list_catalog(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    project_code: Optional[str] = Query(None, description="Filter by project (WSOP, HCL, etc.)"),
    year: Optional[int] = Query(None, description="Filter by year"),
    search: Optional[str] = Query(None, description="Search in title and filename"),
    include_hidden: bool = Query(False, description="Include hidden files"),
    version_type: Optional[str] = Query(None, description="Filter by version type"),
    file_format: Optional[str] = Query(None, description="Filter by format (mp4, mov, etc.)"),
    db: Session = Depends(get_db),
) -> CatalogListResponse:
    """
    Browse the video catalog in flat-list format.

    Returns paginated video files with their project/event context embedded.
    Each item includes a human-readable `display_title` and the original `file_name`.

    **Filters:**
    - `project_code`: Filter by project (WSOP, HCL, GGMILLIONS, MPP, PAD, GOG)
    - `year`: Filter by year
    - `search`: Search in display_title and file_name
    - `include_hidden`: Include hidden files (default: false)
    - `version_type`: Filter by version (clean, mastered, stream, etc.)
    - `file_format`: Filter by format (mp4, mov, mxf, etc.)

    **Pagination:**
    - Results are ordered by project, year (desc), then title
    - Default: 20 items per page, max: 100
    """
    service = CatalogService(db)
    result = service.get_catalog_items(
        page=page,
        page_size=page_size,
        project_code=project_code,
        year=year,
        search=search,
        include_hidden=include_hidden,
        version_type=version_type,
        file_format=file_format,
    )

    return CatalogListResponse(
        items=[CatalogItemResponse(**item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get("/stats", response_model=CatalogStatsResponse)
def get_catalog_stats(
    include_hidden: bool = Query(False, description="Include hidden files in stats"),
    db: Session = Depends(get_db),
) -> CatalogStatsResponse:
    """
    Get catalog statistics.

    Returns file counts grouped by project, year, and format.
    Also includes total duration and size if available.
    """
    service = CatalogService(db)
    stats = service.get_catalog_stats(include_hidden=include_hidden)

    return CatalogStatsResponse(**stats)


@router.get("/filters")
def get_filter_options(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get available filter options for catalog UI.

    Returns distinct values for:
    - projects: Available project codes with names
    - years: Available years
    - formats: Available file formats
    - version_types: Available version types
    """
    service = CatalogService(db)
    return service.get_filter_options()


@router.get("/groups")
def get_catalog_groups(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Groups per page"),
    project_code: Optional[str] = Query(None, description="Filter by project"),
    content_type: Optional[str] = Query(None, description="Filter by content type (full_episode, hand_clip)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get catalog groups (Netflix-style grouped view).

    Returns groups by catalog_title with episode counts.
    Each group represents a collection like "WSOP 2024 Main Event" with multiple episodes.

    **Filters:**
    - `project_code`: Filter by project (WSOP, HCL, etc.)
    - `content_type`: Filter by type (full_episode, hand_clip)
    """
    service = CatalogService(db)
    return service.get_catalog_groups(
        page=page,
        page_size=page_size,
        project_code=project_code,
        content_type=content_type,
    )


@router.get("/groups/{catalog_title}/episodes")
def get_catalog_group_episodes(
    catalog_title: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Episodes per page"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get episodes within a catalog group.

    Returns individual episodes/clips for a specific catalog group.

    **Example:**
    - GET /api/catalog/groups/WSOP%202024%20Main%20Event/episodes
    - Returns: Day 1A, Day 1B, Day 2, Final Table, etc.
    """
    service = CatalogService(db)
    result = service.get_catalog_group_episodes(
        catalog_title=catalog_title,
        page=page,
        page_size=page_size,
    )

    if result["total"] == 0:
        raise HTTPException(status_code=404, detail=f"Catalog group not found: {catalog_title}")

    return result


@router.get("/{video_id}", response_model=CatalogItemResponse)
def get_catalog_item(
    video_id: UUID,
    db: Session = Depends(get_db),
) -> CatalogItemResponse:
    """
    Get a single catalog item by video file ID.

    Returns the video file with its full context (project, event, episode).
    """
    service = CatalogService(db)
    item = service.get_catalog_item(video_id)

    if not item:
        raise HTTPException(status_code=404, detail="Video file not found")

    return CatalogItemResponse(**item)
