"""
API Package

FastAPI routers for all endpoints.
"""
from src.api.projects import router as projects_router
from src.api.seasons import router as seasons_router
from src.api.events import router as events_router
from src.api.episodes import router as episodes_router
from src.api.health import router as health_router
from src.api.sync import router as sync_router
from src.api.scheduler import router as scheduler_router
from src.api.catalog import router as catalog_router
from src.api.websocket import router as websocket_router
from src.api.dashboard import router as dashboard_router

__all__ = [
    "projects_router",
    "seasons_router",
    "events_router",
    "episodes_router",
    "health_router",
    "sync_router",
    "scheduler_router",
    "catalog_router",
    "websocket_router",
    "dashboard_router",
]
