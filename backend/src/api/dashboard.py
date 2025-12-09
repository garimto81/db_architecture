"""
Dashboard API for frontend monitoring

Provides endpoints for:
- Dashboard statistics
- System health check
- Sync status overview

BLOCK_FRONTEND에서 호출하는 대시보드 데이터 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from src.database import get_db
from src.models.video_file import VideoFile
from src.models.project import Project
from src.api.websocket import get_connection_count

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# Pydantic schemas for responses
class StorageUsage(BaseModel):
    total_size_gb: float
    by_project: Dict[str, float]


class SyncLogEntry(BaseModel):
    id: str
    timestamp: str
    source: str
    type: str
    message: str
    details: Optional[Dict[str, Any]] = None


class DashboardStatsResponse(BaseModel):
    total_files: int
    total_hand_clips: int
    total_catalogs: int
    by_project: Dict[str, int]
    by_year: Dict[str, int]
    recent_syncs: List[SyncLogEntry]
    storage_usage: StorageUsage


class DatabaseHealth(BaseModel):
    connected: bool
    latency_ms: float


class NasHealth(BaseModel):
    accessible: bool
    path: str


class SchedulerHealth(BaseModel):
    running: bool
    jobs_count: int


class HealthResponse(BaseModel):
    status: str  # healthy, degraded, unhealthy
    database: DatabaseHealth
    nas: NasHealth
    scheduler: SchedulerHealth
    websocket_connections: int
    timestamp: str


@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Get dashboard statistics.

    Returns aggregated statistics for the video catalog:
    - Total file counts
    - Files by project
    - Files by year
    - Recent sync activities
    - Storage usage estimates
    """
    # Total files count (exclude hidden and deleted)
    total_files = db.query(func.count(VideoFile.id)).filter(
        VideoFile.deleted_at.is_(None),
        VideoFile.is_hidden == False
    ).scalar() or 0

    # Files by project - extract from catalog_title prefix or file_path
    # Since VideoFile doesn't have project_code directly, we use catalog_title
    by_project_query = (
        db.query(VideoFile.catalog_title, func.count(VideoFile.id))
        .filter(
            VideoFile.deleted_at.is_(None),
            VideoFile.is_hidden == False,
            VideoFile.catalog_title.isnot(None)
        )
        .group_by(VideoFile.catalog_title)
        .all()
    )

    # Extract project codes from catalog_titles (e.g., "WSOP 2024 Main Event" -> "WSOP")
    project_counts: Dict[str, int] = {}
    for catalog_title, count in by_project_query:
        if catalog_title:
            # First word is usually the project code
            project_code = catalog_title.split()[0] if catalog_title else "OTHER"
            project_counts[project_code] = project_counts.get(project_code, 0) + count

    # If no catalog_titles, try to extract from file_path
    if not project_counts:
        # Fallback: count files by version_type as placeholder
        by_version_query = (
            db.query(VideoFile.version_type, func.count(VideoFile.id))
            .filter(
                VideoFile.deleted_at.is_(None),
                VideoFile.is_hidden == False
            )
            .group_by(VideoFile.version_type)
            .all()
        )
        project_counts = {row[0] or "unknown": row[1] for row in by_version_query}

    # Files by year - extract from catalog_title or use placeholder
    by_year: Dict[str, int] = {}

    # Estimate storage usage
    avg_file_size_gb = 2.5  # Estimated average file size in GB
    total_size_gb = total_files * avg_file_size_gb

    storage_by_project = {
        project: count * avg_file_size_gb / 1000  # Convert to TB
        for project, count in project_counts.items()
    }

    # Recent syncs (placeholder - would come from sync_logs table)
    recent_syncs: List[SyncLogEntry] = []

    # Catalog count - count unique catalog_titles
    total_catalogs = db.query(func.count(func.distinct(VideoFile.catalog_title))).filter(
        VideoFile.deleted_at.is_(None),
        VideoFile.is_hidden == False,
        VideoFile.catalog_title.isnot(None)
    ).scalar() or 0

    # Hand clips count
    total_hand_clips = db.query(func.count(VideoFile.id)).filter(
        VideoFile.deleted_at.is_(None),
        VideoFile.content_type == "hand_clip"
    ).scalar() or 0

    return DashboardStatsResponse(
        total_files=total_files,
        total_hand_clips=total_hand_clips,
        total_catalogs=total_catalogs,
        by_project=project_counts,
        by_year=by_year,
        recent_syncs=recent_syncs,
        storage_usage=StorageUsage(
            total_size_gb=total_size_gb / 1000,  # Convert to TB
            by_project=storage_by_project,
        ),
    )


@router.get("/health", response_model=HealthResponse)
def get_system_health(db: Session = Depends(get_db)):
    """
    Get system health status.

    Checks:
    - Database connectivity and latency
    - NAS accessibility (placeholder)
    - Scheduler status (placeholder)
    - WebSocket connections count
    """
    # Check database connectivity
    db_connected = False
    db_latency_ms = 0.0

    try:
        start = datetime.now()
        db.execute(text("SELECT 1"))
        db_latency_ms = (datetime.now() - start).total_seconds() * 1000
        db_connected = True
    except Exception as e:
        print(f"[Health] Database check failed: {e}")

    # NAS check (placeholder - would use os.path.exists or SMB connection)
    nas_accessible = True  # Placeholder
    nas_path = "//NAS/GGPOKER"  # From config

    # Scheduler check (placeholder - would check APScheduler status)
    scheduler_running = True  # Placeholder
    scheduler_jobs = 2  # Placeholder (NAS sync + Sheets sync)

    # WebSocket connections
    ws_connections = get_connection_count()

    # Determine overall status
    if db_connected and nas_accessible and scheduler_running:
        status = "healthy"
    elif db_connected:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        database=DatabaseHealth(
            connected=db_connected,
            latency_ms=round(db_latency_ms, 2),
        ),
        nas=NasHealth(
            accessible=nas_accessible,
            path=nas_path,
        ),
        scheduler=SchedulerHealth(
            running=scheduler_running,
            jobs_count=scheduler_jobs,
        ),
        websocket_connections=ws_connections,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/sync/status")
def get_sync_status(db: Session = Depends(get_db)):
    """
    Get current sync status for NAS and Google Sheets.

    Returns the current state of sync operations and next scheduled times.
    """
    # Get file counts
    nas_files_count = db.query(func.count(VideoFile.id)).filter(
        VideoFile.deleted_at.is_(None)
    ).scalar() or 0

    # Placeholder values - would come from sync state storage
    now = datetime.utcnow()
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    return {
        "nas": {
            "last_sync": (now - timedelta(hours=1)).isoformat(),  # Placeholder
            "status": "idle",
            "files_count": nas_files_count,
            "next_scheduled": next_hour.isoformat(),
        },
        "sheets": {
            "last_sync": (now - timedelta(hours=1)).isoformat(),  # Placeholder
            "status": "idle",
            "rows_count": 0,  # Placeholder
            "next_scheduled": next_hour.isoformat(),
        },
        "scheduler": {
            "is_running": True,
            "jobs": [
                {
                    "id": "nas_sync",
                    "name": "NAS Folder Sync",
                    "next_run": next_hour.isoformat(),
                    "interval_seconds": 3600,
                },
                {
                    "id": "sheets_sync",
                    "name": "Google Sheets Sync",
                    "next_run": next_hour.isoformat(),
                    "interval_seconds": 3600,
                },
            ],
        },
    }
