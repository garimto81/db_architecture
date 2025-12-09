"""
Pytest Configuration and Fixtures

Provides test database setup and common fixtures.
"""
import pytest
from datetime import datetime, date
from uuid import uuid4
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Use SQLite in-memory for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Create a test-specific Base without schema
TestBase = declarative_base()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Setup test database schema once for all tests."""
    # Import models to get table definitions
    from src.models import Project, Season, Event, Episode, VideoFile
    from src.database import Base

    # Create copies of tables without schema for SQLite
    for table_name, table in list(Base.metadata.tables.items()):
        table.schema = None

    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    yield

    # Cleanup
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session(setup_test_database):
    """Create a fresh database session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database override."""
    # Import here to avoid PostgreSQL connection at module load
    from src.database import get_db
    from src.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Override the lifespan to skip DB initialization
    original_lifespan = app.router.lifespan_context

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def test_lifespan(app):
        # Skip database initialization in tests
        yield

    app.router.lifespan_context = test_lifespan
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


@pytest.fixture
def sample_project(db_session):
    """Create a sample project for testing."""
    from src.models import Project

    project = Project(
        id=uuid4(),
        code="WSOP",
        name="World Series of Poker",
        description="The most prestigious poker tournament series",
        nas_base_path="/nas/wsop",
        is_active=True,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def sample_season(db_session, sample_project):
    """Create a sample season for testing."""
    from src.models import Season

    season = Season(
        id=uuid4(),
        project_id=sample_project.id,
        year=2024,
        name="WSOP 2024",
        location="Las Vegas",
        sub_category="BRACELET_LV",
        status="active",
    )
    db_session.add(season)
    db_session.commit()
    db_session.refresh(season)
    return season


@pytest.fixture
def sample_event(db_session, sample_season):
    """Create a sample event for testing."""
    from src.models import Event

    event = Event(
        id=uuid4(),
        season_id=sample_season.id,
        event_number=1,
        name="$10,000 No-Limit Hold'em Main Event",
        name_short="Main Event",
        event_type="main_event",
        game_type="NLHE",
        buy_in=10000,
        venue="Paris Las Vegas",
        status="completed",
        start_date=date(2024, 7, 3),
        end_date=date(2024, 7, 17),
        total_days=15,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


@pytest.fixture
def sample_episode(db_session, sample_event):
    """Create a sample episode for testing."""
    from src.models import Episode

    episode = Episode(
        id=uuid4(),
        event_id=sample_event.id,
        episode_number=1,
        day_number=1,
        part_number=1,
        title="Main Event Day 1 - Part 1",
        episode_type="full",
        duration_seconds=7200,
    )
    db_session.add(episode)
    db_session.commit()
    db_session.refresh(episode)
    return episode


@pytest.fixture
def sample_video_file(db_session, sample_episode):
    """Create a sample video file for testing."""
    from src.models import VideoFile

    video_file = VideoFile(
        id=uuid4(),
        episode_id=sample_episode.id,
        file_path="/nas/wsop/2024/main_event/day1_part1.mp4",
        file_name="day1_part1.mp4",
        file_size_bytes=5_000_000_000,
        file_format="mp4",
        resolution="1920x1080",
        video_codec="h264",
        audio_codec="aac",
        duration_seconds=7200,
        version_type="clean",
        is_original=True,
        scan_status="scanned",
    )
    db_session.add(video_file)
    db_session.commit()
    db_session.refresh(video_file)
    return video_file


@pytest.fixture
def full_hierarchy(
    db_session,
    sample_project,
    sample_season,
    sample_event,
    sample_episode,
    sample_video_file,
):
    """Create a complete data hierarchy for testing."""
    return {
        "project": sample_project,
        "season": sample_season,
        "event": sample_event,
        "episode": sample_episode,
        "video_file": sample_video_file,
    }
