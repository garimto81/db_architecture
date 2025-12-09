"""
GGP Poker Video Catalog API

FastAPI application for managing poker video catalog data.
"""
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.database import engine, Base
from src.api import (
    projects_router,
    seasons_router,
    events_router,
    episodes_router,
    health_router,
    sync_router,
    scheduler_router,
    catalog_router,
    websocket_router,
    dashboard_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup: Create tables if they don't exist
    # Note: In production, use Alembic migrations instead
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    GGP Poker Video Catalog API

    API for managing poker video content organized by:
    - **Projects**: Top-level content categories (WSOP, HCL, GGMILLIONS, etc.)
    - **Seasons**: Yearly/periodic collections within projects
    - **Events**: Individual tournaments or show episodes
    - **Episodes**: Video content units
    - **Video Files**: Physical media files

    ## Features
    - Hierarchical content organization
    - Filtering and pagination
    - Project statistics
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
cors_origins = json.loads(settings.cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(projects_router)
app.include_router(seasons_router)
app.include_router(events_router)
app.include_router(episodes_router)
app.include_router(health_router)
app.include_router(sync_router)
app.include_router(scheduler_router)
app.include_router(catalog_router)
app.include_router(websocket_router)
app.include_router(dashboard_router)


@app.get("/", tags=["health"])
def root():
    """Root endpoint returning API info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["health"])
def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}
