"""
Seasons API Router

Endpoints for Season operations.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.services.season_service import SeasonService
from src.schemas.season import (
    SeasonWithProjectResponse,
    SeasonFilter,
)
from src.schemas.common import (
    PaginatedResponse,
    PaginationParams,
    ProjectCode,
    SeasonStatus,
)

router = APIRouter(prefix="/api/seasons", tags=["seasons"])


@router.get("", response_model=PaginatedResponse[SeasonWithProjectResponse])
def list_seasons(
    project_code: Optional[ProjectCode] = Query(None, description="Filter by project code"),
    year: Optional[int] = Query(None, ge=1973, le=2030, description="Filter by year"),
    sub_category: Optional[str] = Query(None, description="Filter by sub_category (WSOP only)"),
    status: Optional[SeasonStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SeasonWithProjectResponse]:
    """
    Get seasons with optional filtering and pagination.

    - **project_code**: Filter by project (WSOP, HCL, GGMILLIONS, etc.)
    - **year**: Filter by season year (1973-2030)
    - **sub_category**: Filter by sub_category (WSOP only: ARCHIVE, BRACELET_LV, etc.)
    - **status**: Filter by status (active, completed, upcoming)
    """
    service = SeasonService(db)

    filters = SeasonFilter(
        project_code=project_code,
        year=year,
        sub_category=sub_category,
        status=status,
    )

    pagination = PaginationParams(page=page, page_size=page_size)

    return service.list_seasons(filters=filters, pagination=pagination)
