"""
Health & Monitoring API Router

Endpoints for database health checks and statistics.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import text, func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.database import get_db
from src.models import Project, Season, Event, Episode, VideoFile

router = APIRouter(prefix="/api/health", tags=["health"])


class DatabaseStats(BaseModel):
    """Database statistics response"""
    status: str
    connected: bool
    response_time_ms: float
    database_name: str
    database_size: Optional[str] = None
    tables: dict


class TableStats(BaseModel):
    """Individual table statistics"""
    name: str
    row_count: int


class FullHealthResponse(BaseModel):
    """Complete health check response"""
    status: str
    timestamp: datetime
    database: DatabaseStats
    api_version: str


@router.get("/db", response_model=FullHealthResponse)
def check_database_health(db: Session = Depends(get_db)) -> FullHealthResponse:
    """
    Database health check with detailed statistics.

    Returns:
    - Connection status
    - Response time
    - Table row counts
    - Database size (PostgreSQL only)
    """
    from src.config import settings
    import time

    start_time = time.time()
    connected = False
    db_size = None
    tables_stats = {}

    try:
        # Test connection with simple query
        db.execute(text("SELECT 1"))
        connected = True

        # Get table counts
        tables_stats = {
            "projects": db.execute(select(func.count(Project.id))).scalar() or 0,
            "seasons": db.execute(select(func.count(Season.id))).scalar() or 0,
            "events": db.execute(select(func.count(Event.id))).scalar() or 0,
            "episodes": db.execute(select(func.count(Episode.id))).scalar() or 0,
            "video_files": db.execute(select(func.count(VideoFile.id))).scalar() or 0,
        }

        # Try to get database size (PostgreSQL specific)
        try:
            result = db.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))"))
            db_size = result.scalar()
        except Exception:
            # SQLite or other DB doesn't support this
            db_size = "N/A"

    except Exception as e:
        connected = False
        tables_stats = {"error": str(e)}

    response_time = (time.time() - start_time) * 1000  # Convert to ms

    return FullHealthResponse(
        status="healthy" if connected else "unhealthy",
        timestamp=datetime.now(),
        database=DatabaseStats(
            status="connected" if connected else "disconnected",
            connected=connected,
            response_time_ms=round(response_time, 2),
            database_name="pokervod",
            database_size=db_size,
            tables=tables_stats,
        ),
        api_version=settings.app_version,
    )


@router.get("/db/tables")
def get_table_details(db: Session = Depends(get_db)) -> dict:
    """
    Get detailed table statistics.

    Returns row counts and basic info for each table.
    """
    stats = {
        "projects": {
            "total": db.execute(select(func.count(Project.id))).scalar() or 0,
            "active": db.execute(
                select(func.count(Project.id)).where(Project.is_active == True)
            ).scalar() or 0,
        },
        "seasons": {
            "total": db.execute(select(func.count(Season.id))).scalar() or 0,
            "by_status": {},
        },
        "events": {
            "total": db.execute(select(func.count(Event.id))).scalar() or 0,
            "by_status": {},
        },
        "episodes": {
            "total": db.execute(select(func.count(Episode.id))).scalar() or 0,
        },
        "video_files": {
            "total": db.execute(select(func.count(VideoFile.id))).scalar() or 0,
            "total_size_gb": 0.0,
            "total_duration_hours": 0.0,
        },
    }

    # Season status breakdown
    season_statuses = db.execute(
        select(Season.status, func.count(Season.id)).group_by(Season.status)
    ).all()
    stats["seasons"]["by_status"] = {status: count for status, count in season_statuses}

    # Event status breakdown
    event_statuses = db.execute(
        select(Event.status, func.count(Event.id)).group_by(Event.status)
    ).all()
    stats["events"]["by_status"] = {status: count for status, count in event_statuses}

    # Video file aggregates
    video_agg = db.execute(
        select(
            func.coalesce(func.sum(VideoFile.file_size_bytes), 0),
            func.coalesce(func.sum(VideoFile.duration_seconds), 0),
        )
    ).one()

    total_bytes, total_seconds = video_agg
    stats["video_files"]["total_size_gb"] = round((total_bytes or 0) / (1024**3), 2)
    stats["video_files"]["total_duration_hours"] = round((total_seconds or 0) / 3600, 2)

    return stats


@router.get("/db/connections")
def get_connection_info(db: Session = Depends(get_db)) -> dict:
    """
    Get database connection information (PostgreSQL only).

    Returns active connections and pool status.
    """
    try:
        # PostgreSQL specific queries
        active_connections = db.execute(
            text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
        ).scalar()

        max_connections = db.execute(
            text("SHOW max_connections")
        ).scalar()

        return {
            "active_connections": active_connections,
            "max_connections": int(max_connections) if max_connections else None,
            "utilization_percent": round((active_connections / int(max_connections)) * 100, 2) if max_connections else None,
        }
    except Exception as e:
        # SQLite doesn't support these queries
        return {
            "message": "Connection stats not available for this database type",
            "error": str(e),
        }
