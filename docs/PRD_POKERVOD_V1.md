# PRD: PokerVOD - 포커 비디오 카탈로그 시스템

> **버전**: 1.0.0 | **작성일**: 2025-12-11 | **상태**: Draft

---

## 1. Executive Summary

### 1.1 프로젝트 개요

**PokerVOD**는 GGP Production의 포커 영상 콘텐츠를 체계적으로 관리하는 비디오 카탈로그 시스템입니다. NAS 스토리지의 영상 파일과 Google Sheets의 핸드 분석 데이터를 통합하여 Netflix 스타일의 미디어 라이브러리를 구축합니다.

### 1.2 비즈니스 목표

| 목표 | 설명 |
|------|------|
| **콘텐츠 통합 관리** | 6개 포커 시리즈 (WSOP, HCL, GGMillions 등) 중앙 집중 관리 |
| **메타데이터 자동화** | 파일명 파싱 → 자동 분류 → 검색 최적화 |
| **핸드 분석 연동** | Google Sheets 핸드 데이터 ↔ 영상 타임코드 매핑 |
| **OTT 서비스 준비** | 카탈로그 기반 스트리밍 서비스 확장 가능 |

### 1.3 기술 스택

| 계층 | 기술 | 버전 |
|------|------|------|
| **Backend** | FastAPI + Python | 3.11+ |
| **Database** | PostgreSQL | 15+ |
| **ORM** | SQLAlchemy | 2.0+ |
| **Migration** | Alembic | 1.13+ |
| **Frontend** | React + TypeScript | 19+ |
| **Container** | Docker Compose | 3.8+ |

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           POKERVOD SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│  │  NAS Storage │     │Google Sheets │     │  PostgreSQL  │            │
│  │  (19TB+)     │     │  (2 Sheets)  │     │   Database   │            │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘            │
│         │                    │                    │                     │
│         ▼                    ▼                    ▼                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      FastAPI Backend                             │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │   │
│  │  │  NAS Sync │  │  Sheets   │  │  Catalog  │  │   REST    │    │   │
│  │  │  Service  │  │  Service  │  │  Service  │  │    API    │    │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    React Dashboard                               │   │
│  │          Catalog Browser │ Sync Monitor │ Admin Panel            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Design Principles

| 원칙 | 설명 |
|------|------|
| **Schema as Code** | ORM 모델이 유일한 스키마 정의 (Single Source of Truth) |
| **Type Safety** | SQLAlchemy 2.0 Mapped 패턴으로 완전한 타입 안전성 |
| **Migration First** | 모든 스키마 변경은 Alembic 마이그레이션으로 관리 |
| **ORM Only** | Raw SQL 사용 금지, 모든 쿼리는 ORM으로 작성 |
| **Service Layer** | 비즈니스 로직은 Service 계층에 집중 |

---

## 3. Database Schema

### 3.1 Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CORE ENTITIES                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Project ──1:N──▶ Season ──1:N──▶ Event ──1:N──▶ Episode                │
│     │                                              │                     │
│     │                                              ├──1:N──▶ VideoFile  │
│     │                                              │              │      │
│     │                                              └──1:N──▶ HandClip   │
│     │                                                          │        │
│     │                                                          ▼        │
│     └──────────────────────────────────────────────────▶ NASFile        │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                           SYNC ENTITIES                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  GoogleSheetSync ◀───── 동기화 상태 추적                                 │
│                                                                          │
│  NASFolder ──1:N──▶ NASFile ◀───── NAS 인벤토리                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Model Definitions

#### 3.2.1 Base Configuration

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import MetaData, func
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

class Base(DeclarativeBase):
    """Global declarative base with naming conventions."""

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )

class TimestampMixin:
    """Reusable timestamp columns for all entities."""
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(default=None)
```

#### 3.2.2 Core Models

**Project** - 포커 시리즈 (WSOP, HCL 등)

```python
class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = {"schema": "pokervod"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    nas_base_path: Mapped[Optional[str]] = mapped_column(String(500))
    filename_pattern: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    seasons: Mapped[List["Season"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan"
    )
```

**Season** - 연도별 시즌

```python
class Season(Base, TimestampMixin):
    __tablename__ = "seasons"
    __table_args__ = {"schema": "pokervod"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("pokervod.projects.id"))
    year: Mapped[int]
    name: Mapped[str] = mapped_column(String(200))
    location: Mapped[Optional[str]] = mapped_column(String(200))
    sub_category: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="seasons")
    events: Mapped[List["Event"]] = relationship(back_populates="season")
```

**Event** - 토너먼트/이벤트

```python
class Event(Base, TimestampMixin):
    __tablename__ = "events"
    __table_args__ = {"schema": "pokervod"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    season_id: Mapped[UUID] = mapped_column(ForeignKey("pokervod.seasons.id"))
    event_number: Mapped[Optional[int]]
    name: Mapped[str] = mapped_column(String(500))
    event_type: Mapped[Optional[str]] = mapped_column(String(50))
    game_type: Mapped[Optional[str]] = mapped_column(String(50))
    buy_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20), default="upcoming")

    # Relationships
    season: Mapped["Season"] = relationship(back_populates="events")
    episodes: Mapped[List["Episode"]] = relationship(back_populates="event")
```

**Episode** - 개별 영상 단위

```python
class Episode(Base, TimestampMixin):
    __tablename__ = "episodes"
    __table_args__ = {"schema": "pokervod"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("pokervod.events.id"))
    episode_number: Mapped[Optional[int]]
    day_number: Mapped[Optional[int]]
    title: Mapped[Optional[str]] = mapped_column(String(500))
    episode_type: Mapped[Optional[str]] = mapped_column(String(50))
    table_type: Mapped[Optional[str]] = mapped_column(String(50))
    duration_seconds: Mapped[Optional[int]]

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="episodes")
    video_files: Mapped[List["VideoFile"]] = relationship(back_populates="episode")
    hand_clips: Mapped[List["HandClip"]] = relationship(back_populates="episode")
```

**VideoFile** - 비디오 파일 메타데이터

```python
class VideoFile(Base, TimestampMixin):
    __tablename__ = "video_files"
    __table_args__ = {"schema": "pokervod"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    episode_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("pokervod.episodes.id", ondelete="SET NULL")
    )

    # File info
    file_path: Mapped[str] = mapped_column(String(1000), unique=True)
    file_name: Mapped[str] = mapped_column(String(500))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    file_format: Mapped[Optional[str]] = mapped_column(String(20))
    file_mtime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Video metadata
    resolution: Mapped[Optional[str]] = mapped_column(String(20))
    duration_seconds: Mapped[Optional[int]]
    version_type: Mapped[Optional[str]] = mapped_column(String(20))

    # Catalog display
    display_title: Mapped[Optional[str]] = mapped_column(String(500))
    content_type: Mapped[Optional[str]] = mapped_column(String(20))
    is_catalog_item: Mapped[bool] = mapped_column(default=False)

    # Filtering
    is_hidden: Mapped[bool] = mapped_column(default=False)
    hidden_reason: Mapped[Optional[str]] = mapped_column(String(50))
    scan_status: Mapped[str] = mapped_column(String(20), default="pending")

    # Relationships
    episode: Mapped[Optional["Episode"]] = relationship(back_populates="video_files")
    hand_clips: Mapped[List["HandClip"]] = relationship(back_populates="video_file")
    nas_file: Mapped[Optional["NASFile"]] = relationship(back_populates="video_file")
```

#### 3.2.3 Hand Clip Models

**HandClip** - 핸드 분석 클립

```python
class HandClip(Base, TimestampMixin):
    __tablename__ = "hand_clips"
    __table_args__ = (
        UniqueConstraint("sheet_source", "sheet_row_number"),
        {"schema": "pokervod"}
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    episode_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("pokervod.episodes.id", ondelete="SET NULL")
    )
    video_file_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("pokervod.video_files.id", ondelete="SET NULL")
    )

    # Sheet tracking
    sheet_source: Mapped[Optional[str]] = mapped_column(String(50))
    sheet_row_number: Mapped[Optional[int]]

    # Content
    title: Mapped[Optional[str]] = mapped_column(String(500))
    timecode: Mapped[Optional[str]] = mapped_column(String(20))
    timecode_end: Mapped[Optional[str]] = mapped_column(String(20))
    duration_seconds: Mapped[Optional[int]]
    notes: Mapped[Optional[str]] = mapped_column(Text)
    hand_grade: Mapped[Optional[str]] = mapped_column(String(10))
    pot_size: Mapped[Optional[int]]

    # Relationships
    episode: Mapped[Optional["Episode"]] = relationship(back_populates="hand_clips")
    video_file: Mapped[Optional["VideoFile"]] = relationship(back_populates="hand_clips")
```

**GoogleSheetSync** - 동기화 상태 추적

```python
class GoogleSheetSync(Base, TimestampMixin):
    __tablename__ = "google_sheet_sync"
    __table_args__ = (
        UniqueConstraint("sheet_id", "entity_type"),
        {"schema": "pokervod"}
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sheet_id: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    last_row_synced: Mapped[int] = mapped_column(default=0)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
```

#### 3.2.4 NAS Inventory Models

**NASFolder** - 폴더 구조

```python
class NASFolder(Base, TimestampMixin):
    __tablename__ = "nas_folders"
    __table_args__ = {"schema": "pokervod"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    folder_path: Mapped[str] = mapped_column(String(1000), unique=True)
    folder_name: Mapped[str] = mapped_column(String(500))
    parent_path: Mapped[Optional[str]] = mapped_column(String(1000))
    depth: Mapped[int] = mapped_column(default=0)

    # Statistics
    file_count: Mapped[int] = mapped_column(default=0)
    folder_count: Mapped[int] = mapped_column(default=0)
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Metadata
    is_empty: Mapped[bool] = mapped_column(default=True)
    is_hidden_folder: Mapped[bool] = mapped_column(default=False)

    # Relationships
    files: Mapped[List["NASFile"]] = relationship(back_populates="folder")
```

**NASFile** - 파일 인벤토리

```python
class NASFile(Base, TimestampMixin):
    __tablename__ = "nas_files"
    __table_args__ = {"schema": "pokervod"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    file_path: Mapped[str] = mapped_column(String(1000), unique=True)
    file_name: Mapped[str] = mapped_column(String(500))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    file_extension: Mapped[Optional[str]] = mapped_column(String(20))
    file_mtime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Classification
    file_category: Mapped[str] = mapped_column(String(20), default="other")
    is_hidden_file: Mapped[bool] = mapped_column(default=False)

    # Foreign keys
    video_file_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("pokervod.video_files.id", ondelete="SET NULL")
    )
    folder_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("pokervod.nas_folders.id", ondelete="SET NULL")
    )

    # Relationships
    video_file: Mapped[Optional["VideoFile"]] = relationship(back_populates="nas_file")
    folder: Mapped[Optional["NASFolder"]] = relationship(back_populates="files")
```

### 3.3 Schema Summary

| Model | Table | Columns | Relationships |
|-------|-------|---------|---------------|
| Project | projects | 9 | → seasons |
| Season | seasons | 10 | → project, events |
| Event | events | 12 | → season, episodes |
| Episode | episodes | 11 | → event, video_files, hand_clips |
| VideoFile | video_files | 18 | → episode, hand_clips, nas_file |
| HandClip | hand_clips | 14 | → episode, video_file |
| GoogleSheetSync | google_sheet_sync | 7 | - |
| NASFolder | nas_folders | 11 | → files |
| NASFile | nas_files | 11 | → video_file, folder |

**Total: 9 Models, 103 Columns**

---

## 4. Migration System

### 4.1 Alembic Configuration

```
backend/
├── alembic/
│   ├── versions/           # Migration scripts
│   │   └── 001_initial_schema.py
│   ├── env.py              # Migration environment
│   └── script.py.mako      # Script template
├── alembic.ini             # Alembic config
└── src/
    └── models/             # ORM models (Source of Truth)
```

### 4.2 Migration Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                     MIGRATION WORKFLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Modify Model ─────────────────────────────────────────────▶ │
│     src/models/*.py                                              │
│                                                                  │
│  2. Generate Migration ───────────────────────────────────────▶ │
│     $ alembic revision --autogenerate -m "description"           │
│                                                                  │
│  3. Review Script ────────────────────────────────────────────▶ │
│     alembic/versions/xxx_description.py                          │
│                                                                  │
│  4. Test Migration ───────────────────────────────────────────▶ │
│     $ alembic upgrade head                                       │
│     $ alembic downgrade -1                                       │
│     $ alembic upgrade head                                       │
│                                                                  │
│  5. Commit ───────────────────────────────────────────────────▶ │
│     Model changes + Migration script                             │
│                                                                  │
│  6. Deploy ───────────────────────────────────────────────────▶ │
│     CI/CD runs: alembic upgrade head                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Docker Integration

```yaml
# docker-compose.yml
services:
  api:
    build: .
    command: >
      sh -c "alembic upgrade head &&
             uvicorn src.main:app --host 0.0.0.0 --port 8000"
    depends_on:
      db:
        condition: service_healthy
```

---

## 5. Project Structure

```
pokervod/
├── backend/
│   ├── alembic/                    # Migration system
│   │   ├── versions/
│   │   └── env.py
│   ├── alembic.ini
│   │
│   ├── src/
│   │   ├── models/                 # ORM Models (Source of Truth)
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # DeclarativeBase + Mixins
│   │   │   ├── project.py
│   │   │   ├── season.py
│   │   │   ├── event.py
│   │   │   ├── episode.py
│   │   │   ├── video_file.py
│   │   │   ├── hand_clip.py
│   │   │   ├── google_sheet_sync.py
│   │   │   ├── nas_folder.py
│   │   │   └── nas_file.py
│   │   │
│   │   ├── services/               # Business Logic
│   │   │   ├── project_service.py
│   │   │   ├── catalog_service.py
│   │   │   ├── sync_service.py
│   │   │   ├── hand_clip_service.py
│   │   │   └── nas_inventory_service.py
│   │   │
│   │   ├── api/                    # REST API (ORM Only)
│   │   │   ├── projects.py
│   │   │   ├── catalog.py
│   │   │   ├── sync.py
│   │   │   └── health.py
│   │   │
│   │   ├── schemas/                # Pydantic DTOs
│   │   │   ├── project.py
│   │   │   ├── catalog.py
│   │   │   └── sync.py
│   │   │
│   │   ├── database.py             # DB connection
│   │   └── main.py                 # FastAPI app
│   │
│   ├── tests/
│   │   ├── factories/              # Model factories
│   │   ├── api/
│   │   └── services/
│   │
│   ├── docker/
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   │
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── store/
│   ├── package.json
│   └── Dockerfile
│
└── docs/
    ├── PRD_POKERVOD_V1.md
    └── API_REFERENCE.md
```

---

## 6. API Design

### 6.1 RESTful Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects` | 프로젝트 목록 |
| GET | `/api/projects/{id}` | 프로젝트 상세 |
| GET | `/api/catalog` | 카탈로그 아이템 목록 |
| GET | `/api/catalog/{id}` | 카탈로그 아이템 상세 |
| GET | `/api/sync/status` | 동기화 상태 |
| POST | `/api/sync/trigger/{source}` | 동기화 시작 |
| GET | `/api/sync/hand-clips` | 핸드 클립 목록 |
| GET | `/api/health` | 헬스 체크 |

### 6.2 Query Pattern (ORM Only)

```python
# Service Layer Example
class HandClipService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_source(
        self,
        source: str,
        limit: int = 20,
        cursor: Optional[UUID] = None
    ) -> List[HandClip]:
        stmt = (
            select(HandClip)
            .where(HandClip.sheet_source == source)
            .order_by(HandClip.created_at.desc())
            .limit(limit)
        )
        if cursor:
            stmt = stmt.where(HandClip.id > cursor)

        return self.db.execute(stmt).scalars().all()
```

---

## 7. Data Sources

### 7.1 NAS Storage

| 프로젝트 | 경로 | 예상 파일 수 | 용량 |
|----------|------|-------------|------|
| WSOP | `/ARCHIVE/WSOP/` | 1,200+ | 18TB |
| HCL | `/ARCHIVE/HCL/` | 100+ | 1TB |
| GGMillions | `/ARCHIVE/GGMillions/` | 15 | 100GB |
| GOG | `/ARCHIVE/GOG 최종/` | 25 | 50GB |
| MPP | `/ARCHIVE/MPP/` | 15 | 100GB |
| PAD | `/ARCHIVE/PAD/` | 45 | 200GB |

### 7.2 Google Sheets

| Sheet | 내용 | 행 수 |
|-------|------|-------|
| metadata_archive | 핸드 분석 데이터 | 40+ |
| iconik_metadata | 추가 메타데이터 | 2,500+ |

---

## 8. Development Guidelines

### 8.1 Coding Standards

| 규칙 | 설명 |
|------|------|
| **No Raw SQL** | `text()` 사용 금지, ORM 쿼리만 허용 |
| **Type Hints** | 모든 함수/변수에 타입 힌트 필수 |
| **Mapped Pattern** | SQLAlchemy 2.0 `Mapped[T]` 패턴 사용 |
| **Service Layer** | API → Service → Model 계층 구조 |
| **Factory Tests** | factory_boy로 테스트 데이터 생성 |

### 8.2 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: no-raw-sql
        name: Prevent raw SQL usage
        entry: python scripts/check_raw_sql.py
        language: python
        files: \.py$
        exclude: alembic/
```

### 8.3 Testing Strategy

```python
# tests/factories/hand_clip_factory.py
class HandClipFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = HandClip

    id = factory.LazyFunction(uuid4)
    sheet_source = "metadata_archive"
    title = factory.Faker("sentence")
    hand_grade = factory.Iterator(["★", "★★", "★★★"])
```

---

## 9. Deployment

### 9.1 Docker Compose

```yaml
name: pokervod

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: pokervod
      POSTGRES_USER: pokervod
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pokervod"]

  api:
    build: ./backend
    command: sh -c "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - /nas/ARCHIVE:/nas/ARCHIVE:ro

  frontend:
    build: ./frontend
    ports:
      - "8080:80"
    depends_on:
      - api

volumes:
  postgres_data:
```

### 9.2 CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
jobs:
  test:
    steps:
      - run: pytest tests/ -v --cov
      - run: alembic upgrade head  # Migration test

  deploy:
    needs: test
    steps:
      - run: docker-compose up -d --build
```

---

## 10. Success Metrics

| 지표 | 목표 |
|------|------|
| ORM Model Coverage | 100% (9/9 models) |
| Raw SQL Usage | 0 locations |
| Test Coverage | ≥ 90% |
| API Response Time | < 200ms (p95) |
| Migration Rollback | Always possible |

---

## 11. Timeline

| Phase | 기간 | 산출물 |
|-------|------|--------|
| **Phase 1: Foundation** | Week 1 | ORM Models + Alembic Setup |
| **Phase 2: Backend** | Week 2 | Services + API Endpoints |
| **Phase 3: Frontend** | Week 3 | Dashboard + Catalog UI |
| **Phase 4: Sync** | Week 4 | NAS + Sheets 동기화 |
| **Phase 5: Polish** | Week 5 | Testing + Documentation |

---

**문서 버전**: 1.0.0
**작성일**: 2025-12-11
**상태**: Draft

### 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0.0 | 2025-12-11 | 초기 작성 |
