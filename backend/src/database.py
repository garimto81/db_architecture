"""
Database connection and session management

SQLAlchemy 2.0 style with PostgreSQL support.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import get_settings

settings = get_settings()

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connection before use
    echo=settings.debug,  # Log SQL queries in debug mode
    pool_size=5,
    max_overflow=10
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """
    Dependency for getting database session

    Usage in FastAPI:
        @router.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database (create all tables)"""
    # Import all models to register them with Base
    from src.models import Project, Season, Event, Episode, VideoFile  # noqa
    Base.metadata.create_all(bind=engine)
