# LLD 06: Backend API Design

> **버전**: 1.2.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09 | **수정일**: 2025-12-09

---

## 1. 개요

GGP Poker Video Catalog의 REST API 백엔드 설계 문서.
FastAPI 기반으로 PostgreSQL 데이터베이스에 대한 CRUD 및 조회 기능을 제공합니다.

### 1.1 기술 스택

| 구성요소 | 기술 | 버전 |
|---------|------|------|
| Framework | FastAPI | ≥0.109.0 |
| ORM | SQLAlchemy | ≥2.0.25 |
| Validation | Pydantic | ≥2.5.0 |
| Database | PostgreSQL | 15 |
| Server | Uvicorn | ≥0.27.0 |

### 1.2 API 엔드포인트 요약

| # | Endpoint | Method | 설명 | 구현 파일 |
|---|----------|--------|------|----------|
| 1 | `/api/projects` | GET | 프로젝트 목록 | `api/projects.py` |
| 2 | `/api/projects/{id}` | GET | 프로젝트 상세 | `api/projects.py` |
| 3 | `/api/projects/{id}/stats` | GET | 프로젝트 통계 | `api/projects.py` |
| 4 | `/api/seasons` | GET | 시즌 목록 (필터링) | `api/seasons.py` |
| 5 | `/api/events` | GET | 이벤트 목록 (필터링) | `api/events.py` |
| 6 | `/api/events/{id}` | GET | 이벤트 상세 | `api/events.py` |
| 7 | `/api/events/{id}/episodes` | GET | 이벤트별 에피소드 | `api/events.py` |
| 8 | `/api/episodes/{id}/video-files` | GET | 에피소드별 비디오 | `api/episodes.py` |
| 9 | `/api/health/db` | GET | DB 상태 모니터링 | `api/health.py` |
| 10 | `/api/health/db/tables` | GET | 테이블별 통계 | `api/health.py` |
| 11 | `/api/health/db/connections` | GET | 연결 풀 상태 | `api/health.py` |
| 12 | `/api/sync/nas` | POST | NAS 전체 동기화 | `api/sync.py` |
| 13 | `/api/sync/nas/{project}` | POST | 프로젝트별 NAS 동기화 | `api/sync.py` |
| 14 | `/api/sync/nas/background` | POST | 백그라운드 NAS 동기화 | `api/sync.py` |
| 15 | `/api/sync/status` | GET | NAS 동기화 상태 | `api/sync.py` |
| 16 | `/api/sync/sheets` | POST | Google Sheet 전체 동기화 | `api/sync.py` |
| 17 | `/api/sync/sheets/{key}` | POST | 시트별 동기화 | `api/sync.py` |
| 18 | `/api/sync/sheets/status` | GET | Sheet 동기화 상태 | `api/sync.py` |
| 19 | `/api/scheduler/status` | GET | 스케줄러 상태 | `api/scheduler.py` |
| 20 | `/api/scheduler/schedules` | GET | 스케줄 설정 조회 | `api/scheduler.py` |
| 21 | `/api/scheduler/start` | POST | 스케줄러 시작 | `api/scheduler.py` |
| 22 | `/api/scheduler/stop` | POST | 스케줄러 중지 | `api/scheduler.py` |
| 23 | `/api/scheduler/jobs/{id}/trigger` | POST | 작업 즉시 실행 | `api/scheduler.py` |
| 24 | `/api/scheduler/jobs/{id}/pause` | POST | 작업 일시 정지 | `api/scheduler.py` |
| 25 | `/api/scheduler/jobs/{id}/resume` | POST | 작업 재개 | `api/scheduler.py` |
| 26 | `/api/scheduler/jobs/{id}` | DELETE | 작업 삭제 | `api/scheduler.py` |
| **Catalog API** | | | | |
| 27 | `/api/catalog` | GET | 카탈로그 플랫 리스트 | `api/catalog.py` |
| 28 | `/api/catalog/stats` | GET | 카탈로그 통계 | `api/catalog.py` |
| 29 | `/api/catalog/filters` | GET | 필터 옵션 목록 | `api/catalog.py` |
| 30 | `/api/catalog/groups` | GET | 카탈로그 그룹 목록 | `api/catalog.py` |
| 31 | `/api/catalog/groups/{title}/episodes` | GET | 그룹별 에피소드 | `api/catalog.py` |
| 32 | `/api/catalog/{video_id}` | GET | 비디오 상세 | `api/catalog.py` |

---

## 2. 아키텍처

### 2.1 계층 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client (Frontend)                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/JSON
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    API Routers Layer                         ││
│  │  projects │ seasons │ events │ episodes │ health │ sync │ scheduler││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Services Layer                            ││
│  │  ProjectService │ NasSyncService │ GoogleSheetService │ SyncScheduler││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Schemas Layer (Pydantic)                  ││
│  │  Request/Response DTOs, Validation, Serialization            ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Models Layer (SQLAlchemy)                 ││
│  │  Project │ Season │ Event │ Episode │ VideoFile              ││
│  └─────────────────────────────────────────────────────────────┘│
└───────────────────────────┬─────────────────────────────────────┘
                            │ SQL
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                           │
│                    (pokervod schema)                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 디렉토리 구조

```
backend/
├── docker/
│   ├── docker-compose.yml      # PostgreSQL + API 컨테이너
│   ├── Dockerfile              # FastAPI 앱 이미지
│   └── init.sql                # 초기 스키마 (DDL)
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 앱 진입점
│   ├── config.py               # Pydantic Settings
│   ├── database.py             # SQLAlchemy 엔진/세션
│   ├── models/                 # ORM 모델
│   │   ├── __init__.py
│   │   ├── types.py            # GUID, TimestampMixin
│   │   ├── project.py
│   │   ├── season.py
│   │   ├── event.py
│   │   ├── episode.py
│   │   └── video_file.py
│   ├── schemas/                # Pydantic 스키마
│   │   ├── __init__.py
│   │   ├── common.py           # 페이지네이션, Enum
│   │   ├── project.py
│   │   ├── season.py
│   │   ├── event.py
│   │   └── episode.py
│   ├── api/                    # 라우터
│   │   ├── __init__.py
│   │   ├── projects.py
│   │   ├── seasons.py
│   │   ├── events.py
│   │   ├── episodes.py
│   │   ├── health.py
│   │   ├── sync.py             # NAS/Sheet 동기화 API
│   │   └── scheduler.py        # 스케줄러 관리 API
│   └── services/               # 비즈니스 로직
│       ├── __init__.py
│       ├── project_service.py
│       ├── season_service.py
│       ├── event_service.py
│       ├── sync_service.py         # NAS 동기화 서비스
│       ├── google_sheet_service.py # Google Sheet 동기화
│       └── scheduler_service.py    # APScheduler 관리
├── tests/
│   ├── conftest.py             # pytest fixtures
│   └── api/
│       ├── test_projects.py
│       ├── test_events.py
│       ├── test_health.py
│       ├── test_sync.py        # NAS/Sheet 동기화 테스트
│       └── test_scheduler.py   # 스케줄러 테스트
├── requirements.txt
└── .env.example
```

---

## 3. 설정 관리

### 3.1 Settings (config.py)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # App
    app_name: str = "GGP Poker Video Catalog API"
    app_version: str = "1.0.0"
    debug: bool = True

    # Database
    database_url: str = "postgresql://pokervod:pokervod123@localhost:5432/pokervod"

    # API
    cors_origins: str = '["http://localhost:3000"]'

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### 3.2 환경 변수

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `DATABASE_URL` | `postgresql://pokervod:pokervod123@localhost:5432/pokervod` | DB 연결 URL |
| `DEBUG` | `true` | 디버그 모드 |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | CORS 허용 origin |

---

## 4. ORM 모델

### 4.1 공통 타입 (types.py)

```python
import uuid
from sqlalchemy import DateTime, func
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declared_attr

class GUID(TypeDecorator):
    """Platform-independent GUID type for UUID columns"""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

class TimestampMixin:
    """Mixin for created_at, updated_at, deleted_at columns"""

    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), default=func.now(), nullable=False)

    @declared_attr
    def updated_at(cls):
        return Column(DateTime(timezone=True), default=func.now(),
                      onupdate=func.now(), nullable=False)

    @declared_attr
    def deleted_at(cls):
        return Column(DateTime(timezone=True), nullable=True)
```

### 4.2 엔티티 관계

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Project   │──1:N─│   Season    │──1:N─│    Event    │
│             │      │             │      │             │
│ id (PK)     │      │ id (PK)     │      │ id (PK)     │
│ code        │      │ project_id  │      │ season_id   │
│ name        │      │ year        │      │ name        │
└─────────────┘      │ name        │      │ event_type  │
                     └─────────────┘      └──────┬──────┘
                                                 │
                                                1:N
                                                 │
                     ┌─────────────┐      ┌──────▼──────┐
                     │  VideoFile  │──N:1─│   Episode   │
                     │             │      │             │
                     │ id (PK)     │      │ id (PK)     │
                     │ episode_id  │      │ event_id    │
                     │ file_path   │      │ title       │
                     └─────────────┘      └─────────────┘
```

---

## 5. Pydantic 스키마

### 5.1 공통 스키마 (common.py)

```python
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List
from enum import Enum

T = TypeVar("T")

class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper"""
    items: List[T]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")

# Enum definitions
class ProjectCode(str, Enum):
    WSOP = "WSOP"
    HCL = "HCL"
    GGMILLIONS = "GGMILLIONS"
    MPP = "MPP"
    PAD = "PAD"
    GOG = "GOG"
    OTHER = "OTHER"

class EventType(str, Enum):
    BRACELET = "bracelet"
    CIRCUIT = "circuit"
    HIGH_ROLLER = "high_roller"
    CASH_GAME = "cash_game"
    TV_SERIES = "tv_series"
    MAIN_EVENT = "main_event"
    # ... 기타 타입
```

### 5.2 응답 스키마 패턴

```python
# Base → Response → DetailResponse 패턴

class EventBase(BaseModel):
    """Base event schema (공통 필드)"""
    name: str = Field(..., max_length=500)
    event_type: Optional[str] = None
    game_type: Optional[str] = None
    buy_in: Optional[Decimal] = Field(None, ge=0)
    # ...

class EventResponse(EventBase):
    """Event response schema (기본 응답)"""
    id: UUID
    season_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class EventDetailResponse(EventResponse):
    """Event detail with parent info (상세 응답)"""
    season_name: str
    season_year: int
    project_code: str
    project_name: str
    episode_count: int = 0
```

---

## 6. API 라우터

### 6.1 라우터 패턴

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.database import get_db
from src.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("", response_model=ProjectListResponse)
def list_projects(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
) -> ProjectListResponse:
    """Get all projects with optional filtering"""
    service = ProjectService(db)
    return service.list_projects(is_active=is_active)

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    """Get a single project by ID"""
    service = ProjectService(db)
    project = service.get_project(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse.model_validate(project)
```

### 6.2 필터링 패턴

```python
class EventFilter(BaseModel):
    """Event filter parameters"""
    season_id: Optional[UUID] = Field(None, description="Filter by season ID")
    event_type: Optional[EventType] = Field(None, description="Filter by event type")
    game_type: Optional[GameType] = Field(None, description="Filter by game type")
    min_buy_in: Optional[Decimal] = Field(None, ge=0, description="Minimum buy-in")
    max_buy_in: Optional[Decimal] = Field(None, ge=0, description="Maximum buy-in")
    status: Optional[str] = Field(None, description="Filter by status")

@router.get("", response_model=PaginatedResponse[EventDetailResponse])
def list_events(
    season_id: Optional[UUID] = Query(None),
    event_type: Optional[EventType] = Query(None),
    game_type: Optional[GameType] = Query(None),
    min_buy_in: Optional[Decimal] = Query(None, ge=0),
    max_buy_in: Optional[Decimal] = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    filters = EventFilter(...)
    pagination = PaginationParams(page=page, page_size=page_size)
    return service.list_events(filters=filters, pagination=pagination)
```

---

## 7. 서비스 계층

### 7.1 서비스 패턴

```python
class ProjectService:
    """Service class for Project operations"""

    def __init__(self, db: Session):
        self.db = db

    def list_projects(self, is_active: Optional[bool] = None) -> ProjectListResponse:
        """Get all projects with optional active filter"""
        query = select(Project).where(Project.deleted_at.is_(None))

        if is_active is not None:
            query = query.where(Project.is_active == is_active)

        query = query.order_by(Project.code)
        result = self.db.execute(query)
        projects = result.scalars().all()

        return ProjectListResponse(
            items=[ProjectResponse.model_validate(p) for p in projects],
            total=len(projects),
        )

    def get_project_stats(self, project_id: UUID) -> ProjectStatsResponse:
        """Get aggregated statistics for a project"""
        # 계층 구조를 따라 집계
        # projects → seasons → events → episodes → video_files
        # ...
```

### 7.2 집계 쿼리 패턴

```python
def get_project_stats(self, project_id: UUID) -> ProjectStatsResponse:
    """프로젝트 통계: 시즌/이벤트/에피소드/비디오 카운트 및 총 용량"""

    # Season 카운트
    season_count = self.db.execute(
        select(func.count(Season.id))
        .where(Season.project_id == project_id)
        .where(Season.deleted_at.is_(None))
    ).scalar()

    # Video 집계 (용량, 재생시간)
    video_stats = self.db.execute(
        select(
            func.count(VideoFile.id),
            func.coalesce(func.sum(VideoFile.duration_seconds), 0),
            func.coalesce(func.sum(VideoFile.file_size_bytes), 0),
        ).where(VideoFile.episode_id.in_(episode_ids))
    ).one()

    return ProjectStatsResponse(
        project_id=project.id,
        total_seasons=season_count,
        total_duration_hours=round(total_seconds / 3600, 2),
        total_size_gb=round(total_bytes / (1024**3), 2),
    )
```

---

## 8. Health Check API

### 8.1 엔드포인트

| Endpoint | 설명 | 응답 |
|----------|------|------|
| `GET /api/health/db` | DB 연결 상태 + 테이블 카운트 | 연결 상태, 응답시간, 테이블별 행 수 |
| `GET /api/health/db/tables` | 상세 테이블 통계 | 상태별 분류, 총 용량, 재생시간 |
| `GET /api/health/db/connections` | 연결 풀 상태 (PostgreSQL) | 활성 연결, 최대 연결, 사용률 |

### 8.2 응답 예시

```json
// GET /api/health/db
{
  "status": "healthy",
  "timestamp": "2025-12-09T15:52:18.994872",
  "database": {
    "status": "connected",
    "connected": true,
    "response_time_ms": 20.67,
    "database_name": "pokervod",
    "database_size": "7965 kB",
    "tables": {
      "projects": 7,
      "seasons": 2,
      "events": 0,
      "episodes": 0,
      "video_files": 0
    }
  },
  "api_version": "1.0.0"
}
```

---

## 9. Sync API

### 9.1 NAS 동기화 서비스 (sync_service.py)

```python
class FileParser:
    """프로젝트별 파일명 파싱"""

    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.mxf'}

    # 프로젝트별 패턴
    WSOP_BRACELET_PATTERN = re.compile(r'^(\d+)-wsop-(\d{4})-be-ev-(\d+)-...')
    GGMILLIONS_PATTERN = re.compile(r'^(\d{6})_(.+?)\.(\w+)$')
    # ... 기타 패턴

    def parse(self, file_path: str, project_code: str) -> ParsedFile:
        """파일명에서 메타데이터 추출"""
        # year, event_number, episode_number, version_type 등

class NasSyncService:
    """NAS 디렉토리 스캔 및 DB 동기화"""

    NAS_PATHS = {
        'WSOP': r'\\10.10.100.122\docker\GGPNAs\ARCHIVE\WSOP',
        'GGMILLIONS': r'\\10.10.100.122\docker\GGPNAs\ARCHIVE\GGMillions',
        # ... 기타 경로
    }

    def scan_project(self, project_code: str) -> ScanResult:
        """프로젝트 디렉토리 스캔 → 계층 생성 → Upsert"""
```

### 9.2 Google Sheet 동기화 서비스 (google_sheet_service.py)

```python
class TagNormalizer:
    """태그 정규화"""

    NORMALIZATIONS = {
        r'preflop[\s_-]?all[\s_-]?in': 'preflop_allin',
        r'bad[\s_-]?beat': 'bad_beat',
        # 30+ 패턴 지원
    }

    @classmethod
    def normalize(cls, tag: str) -> str:
        """'Bad Beat' → 'bad_beat'"""

class GoogleSheetService:
    """Google Sheets 증분 동기화"""

    MAX_REQUESTS_PER_MINUTE = 60
    BATCH_SIZE = 100

    def sync_sheet(self, sheet_key: str) -> SheetSyncResult:
        """시트별 증분 동기화 (row_number 기반)"""
```

### 9.3 Sync API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/sync/nas` | 전체 NAS 동기화 (6개 프로젝트) |
| POST | `/api/sync/nas/{project_code}` | 프로젝트별 NAS 동기화 |
| POST | `/api/sync/nas/background` | 백그라운드 동기화 |
| GET | `/api/sync/status` | NAS 동기화 상태 |
| POST | `/api/sync/sheets` | 전체 Sheet 동기화 |
| POST | `/api/sync/sheets/{sheet_key}` | 시트별 동기화 |
| GET | `/api/sync/sheets/status` | Sheet 동기화 상태 |

---

## 10. Scheduler API

### 10.1 스케줄러 서비스 (scheduler_service.py)

```python
class SyncScheduler:
    """APScheduler 기반 자동 동기화 관리"""

    DEFAULT_SCHEDULES = {
        'nas_scan': ScheduleConfig(
            job_id='nas_scan',
            cron_expression='0 * * * *',  # 매시 정각
            description='NAS 디렉토리 스캔',
        ),
        'sheet_sync': ScheduleConfig(
            job_id='sheet_sync',
            cron_expression='0 * * * *',  # 매시 정각
            description='Google Sheet 동기화',
        ),
        'daily_validation': ScheduleConfig(
            job_id='daily_validation',
            cron_expression='0 3 * * *',  # 매일 03:00
            description='데이터 무결성 검증',
        ),
    }

    def start(self) -> bool:
        """스케줄러 시작"""

    def trigger_job(self, job_id: str) -> bool:
        """작업 즉시 실행"""
```

### 10.2 Scheduler API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/scheduler/status` | 스케줄러 상태 및 작업 목록 |
| GET | `/api/scheduler/schedules` | 설정된 스케줄 조회 |
| POST | `/api/scheduler/start` | 스케줄러 시작 |
| POST | `/api/scheduler/stop` | 스케줄러 중지 |
| POST | `/api/scheduler/jobs/{id}/trigger` | 작업 즉시 실행 |
| POST | `/api/scheduler/jobs/{id}/pause` | 작업 일시 정지 |
| POST | `/api/scheduler/jobs/{id}/resume` | 작업 재개 |
| DELETE | `/api/scheduler/jobs/{id}` | 작업 삭제 |

### 10.3 스케줄 설정

| Job ID | 이름 | Cron | 기본 상태 |
|--------|------|------|----------|
| `nas_scan` | NAS Scan | `0 * * * *` | 활성화 |
| `nas_scan_urgent` | Urgent Scan | `*/15 * * * *` | 비활성화 |
| `sheet_sync` | Sheet Sync | `0 * * * *` | 활성화 |
| `daily_validation` | Validation | `0 3 * * *` | 활성화 |
| `weekly_report` | Weekly Report | `0 4 * * 0` | 비활성화 |

---

## 11. Catalog API (프론트엔드용)

Netflix 스타일의 플랫 리스트 카탈로그를 제공하는 API입니다.
프론트엔드에서 비디오 브라우징 UI를 구현할 때 사용합니다.

### 11.1 핵심 개념

| 개념 | 설명 | 예시 |
|------|------|------|
| **catalog_title** | 그룹 제목 (시리즈/이벤트) | `WSOP 2024 Main Event` |
| **episode_title** | 개별 에피소드 제목 | `Day 1A`, `Ding vs Boianovsky` |
| **content_type** | 콘텐츠 유형 | `full_episode`, `hand_clip` |
| **is_catalog_item** | 대표 파일 여부 | `true` (중복 제거됨) |

### 11.2 엔드포인트 상세

#### GET /api/catalog - 플랫 리스트

모든 비디오 파일을 페이지네이션으로 조회합니다.

**Query Parameters:**

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `page` | int | 1 | 페이지 번호 (1-indexed) |
| `page_size` | int | 20 | 페이지당 항목 수 (max: 100) |
| `project_code` | string | - | 프로젝트 필터 (WSOP, GOG 등) |
| `year` | int | - | 연도 필터 |
| `search` | string | - | 제목/파일명 검색 |
| `include_hidden` | bool | false | 숨김 파일 포함 여부 |
| `version_type` | string | - | 버전 필터 (clean, stream 등) |
| `file_format` | string | - | 포맷 필터 (mp4, mov 등) |

**Response:**

```json
{
  "items": [
    {
      "id": "uuid",
      "display_title": "WSOP 2024 $10K Stud Day 1",
      "file_name": "47-wsop-2024-be-ev-49-10k-stud-day1-001.mp4",
      "file_path": "\\\\nas\\archive\\wsop\\...",
      "duration_seconds": 7200,
      "file_size_bytes": 5368709120,
      "file_format": "mp4",
      "resolution": "1920x1080",
      "version_type": "clean",
      "project_code": "WSOP",
      "project_name": "World Series of Poker",
      "year": 2024,
      "event_name": "$10K Stud Championship",
      "episode_title": "Day 1",
      "is_hidden": false,
      "scan_status": "scanned",
      "created_at": "2025-12-09T10:00:00Z"
    }
  ],
  "total": 815,
  "page": 1,
  "page_size": 20,
  "total_pages": 41
}
```

#### GET /api/catalog/stats - 통계

카탈로그 전체 통계를 조회합니다.

**Response:**

```json
{
  "total_files": 1876,
  "visible_files": 1826,
  "hidden_files": 50,
  "by_project": {
    "WSOP": 1200,
    "GOG": 24,
    "PAD": 500,
    "GGMILLIONS": 152
  },
  "by_year": {
    "2024": 450,
    "2023": 380,
    "2022": 280
  },
  "by_format": {
    "mp4": 1500,
    "mov": 300,
    "mxf": 76
  },
  "total_duration_hours": 2840.5,
  "total_size_gb": 12500.75
}
```

#### GET /api/catalog/filters - 필터 옵션

UI 필터 드롭다운에 표시할 옵션을 조회합니다.

**Response:**

```json
{
  "projects": [
    {"code": "WSOP", "name": "World Series of Poker"},
    {"code": "GOG", "name": "Game of Gold"},
    {"code": "PAD", "name": "Poker After Dark"}
  ],
  "years": [2025, 2024, 2023, 2022, 2021],
  "formats": ["mp4", "mov", "mxf"],
  "version_types": ["clean", "stream", "mastered", "generic"]
}
```

#### GET /api/catalog/groups - 그룹 목록 (Netflix 스타일)

catalog_title로 그룹화된 목록을 조회합니다. **프론트엔드 메인 화면 구현용**

**Query Parameters:**

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `page` | int | 1 | 페이지 번호 |
| `page_size` | int | 20 | 페이지당 그룹 수 |
| `project_code` | string | - | 프로젝트 필터 |
| `content_type` | string | - | 콘텐츠 유형 필터 |

**Response:**

```json
{
  "groups": [
    {
      "catalog_title": "WSOP 2024 Main Event",
      "content_type": "full_episode",
      "episode_count": 8,
      "total_size_gb": 42.5
    },
    {
      "catalog_title": "WSOP 2024 $10K Stud",
      "content_type": "full_episode",
      "episode_count": 2,
      "total_size_gb": 8.2
    },
    {
      "catalog_title": "Game of Gold Season 1",
      "content_type": "full_episode",
      "episode_count": 8,
      "total_size_gb": 24.0
    }
  ],
  "total": 117,
  "page": 1,
  "page_size": 20,
  "total_pages": 6
}
```

#### GET /api/catalog/groups/{catalog_title}/episodes - 그룹 상세

특정 그룹의 에피소드 목록을 조회합니다.

**Path Parameters:**

| 파라미터 | 설명 |
|----------|------|
| `catalog_title` | URL 인코딩된 카탈로그 제목 |

**예시:** `GET /api/catalog/groups/WSOP%202024%20Main%20Event/episodes`

**Response:**

```json
{
  "catalog_title": "WSOP 2024 Main Event",
  "content_type": "full_episode",
  "episodes": [
    {
      "id": "uuid-1",
      "episode_title": "Day 1A",
      "ai_description": "[추후 구현]",
      "version_type": "stream",
      "file_size_gb": 5.2,
      "duration_minutes": 180,
      "file_name": "wsop-2024-me-day1a-stream.mp4",
      "file_path": "\\\\nas\\archive\\..."
    },
    {
      "id": "uuid-2",
      "episode_title": "Day 1B",
      "ai_description": "[추후 구현]",
      "version_type": "stream",
      "file_size_gb": 5.8,
      "duration_minutes": 195,
      "file_name": "wsop-2024-me-day1b-stream.mp4",
      "file_path": "\\\\nas\\archive\\..."
    },
    {
      "id": "uuid-3",
      "episode_title": "Final Table",
      "ai_description": "[추후 구현]",
      "version_type": "clean",
      "file_size_gb": 8.5,
      "duration_minutes": 240,
      "file_name": "wsop-2024-me-ft-clean.mp4",
      "file_path": "\\\\nas\\archive\\..."
    }
  ],
  "total": 8,
  "page": 1,
  "page_size": 50,
  "total_pages": 1
}
```

#### GET /api/catalog/{video_id} - 비디오 상세

단일 비디오 파일의 상세 정보를 조회합니다.

**Response:**

```json
{
  "id": "uuid",
  "display_title": "WSOP 2024 Main Event Day 1A",
  "file_name": "wsop-2024-me-day1a-stream.mp4",
  "file_path": "\\\\nas\\archive\\wsop\\2024\\main-event\\...",
  "duration_seconds": 10800,
  "file_size_bytes": 5583457485,
  "file_format": "mp4",
  "resolution": "1920x1080",
  "version_type": "stream",
  "project_code": "WSOP",
  "project_name": "World Series of Poker",
  "year": 2024,
  "event_name": "Main Event",
  "episode_title": "Day 1A",
  "is_hidden": false,
  "scan_status": "scanned",
  "created_at": "2025-12-09T10:00:00Z",
  "updated_at": "2025-12-09T15:30:00Z"
}
```

### 11.3 프론트엔드 사용 예시

```typescript
// React Query 예시

// 1. 카탈로그 그룹 목록 (메인 화면)
const { data: groups } = useQuery({
  queryKey: ['catalog-groups', { projectCode, page }],
  queryFn: () => fetch(`/api/catalog/groups?project_code=${projectCode}&page=${page}`)
});

// 2. 그룹 내 에피소드 (그룹 클릭 시)
const { data: episodes } = useQuery({
  queryKey: ['catalog-episodes', catalogTitle],
  queryFn: () => fetch(`/api/catalog/groups/${encodeURIComponent(catalogTitle)}/episodes`)
});

// 3. 필터 옵션 (필터 UI)
const { data: filters } = useQuery({
  queryKey: ['catalog-filters'],
  queryFn: () => fetch('/api/catalog/filters')
});

// 4. 검색
const { data: searchResults } = useQuery({
  queryKey: ['catalog-search', searchTerm],
  queryFn: () => fetch(`/api/catalog?search=${searchTerm}`)
});
```

### 11.4 실제 데이터 예시 (2025-12-09)

**카탈로그 그룹 예시:**

| 카탈로그 | 콘텐츠 타입 | 에피소드 수 |
|----------|-------------|-------------|
| GG Millions 2025 | full_episode | 6 |
| WSOP 2024 $10K Stud | full_episode | 2 |
| WSOP 2024 $5K Champions Reunion | full_episode | 2 |
| WSOP 2024 $300 Gladiators | full_episode | 1 |
| WSOP 2024 Main Event Day 2 | hand_clip | 24 |
| Game of Gold Season 1 | full_episode | 8 |
| Poker After Dark Season 12 | full_episode | 44 |

**에피소드 제목 예시:**

| 에피소드 제목 | 카탈로그 | 버전 |
|--------------|----------|------|
| Final Table - Hs Melson Cracks Kks | WSOP 2024 $3K NLH | generic |
| DVORESS vs KUNZE | WSOP 2024 Main Event Day 2 | clean |
| Day8 - Griff Rivers Miracle Queen | WSOP 2024 Main Event | generic |
| Episode 6 | Poker After Dark Season 12 | generic |
| Day 1A | WSOP 2025 $5M GTD Super Circuit | generic |

---

## 12. 테스트 전략

### 11.1 테스트 환경

```python
# conftest.py - SQLite 인메모리로 테스트 격리

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@pytest.fixture(scope="function")
def db_session(setup_test_database):
    """트랜잭션 롤백으로 테스트 격리"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

### 11.2 테스트 케이스 구성

| 테스트 파일 | 테스트 수 | 커버리지 |
|------------|----------|----------|
| `test_projects.py` | 8 | 프로젝트 CRUD, 필터링, 통계 |
| `test_events.py` | 13 | 이벤트 CRUD, 필터링, 에피소드, 비디오 |
| `test_health.py` | 6 | DB 헬스, 테이블 통계, 연결 상태 |
| `test_sync.py` | 19 | NAS/Sheet 동기화, FileParser, TagNormalizer |
| `test_scheduler.py` | 11 | 스케줄러 상태, 스케줄 설정, 작업 관리 |
| **총합** | **57** | API 100% |

---

## 12. Docker 배포

### 12.1 docker-compose.yml

```yaml
services:
  db:
    image: postgres:15-alpine
    container_name: pokervod-db
    environment:
      POSTGRES_DB: pokervod
      POSTGRES_USER: pokervod
      POSTGRES_PASSWORD: pokervod123
    ports:
      - "5432:5432"
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/01-init.sql
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pokervod -d pokervod"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: pokervod-api
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8080:8000"
    environment:
      DATABASE_URL: postgresql://pokervod:pokervod123@db:5432/pokervod
```

### 12.2 실행 명령

```bash
# 시작
cd backend/docker
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down

# 볼륨 포함 삭제
docker-compose down -v
```

---

## 13. API 문서

### 13.1 자동 생성 문서

| URL | 설명 |
|-----|------|
| `http://localhost:8080/docs` | Swagger UI (대화형) |
| `http://localhost:8080/redoc` | ReDoc (정적 문서) |
| `http://localhost:8080/openapi.json` | OpenAPI 스키마 |

---

## 14. 참조

| 문서 | 설명 |
|------|------|
| [01_DATABASE_SCHEMA.md](./01_DATABASE_SCHEMA.md) | DB 스키마 설계 |
| [02_SYNC_SYSTEM.md](./02_SYNC_SYSTEM.md) | 동기화 시스템 |
| [05_AGENT_SYSTEM.md](./05_AGENT_SYSTEM.md) | Block Agent 시스템 |

---

**문서 버전**: 1.2.0
**작성일**: 2025-12-09
**수정일**: 2025-12-09
**상태**: Updated - Catalog API 추가

### 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.2.0 | 2025-12-09 | Catalog API 섹션 추가 (프론트엔드용 Netflix 스타일 API, 6개 엔드포인트) |
| 1.1.0 | 2025-12-09 | Sync API (NAS/Sheet) 및 Scheduler API 추가, 테스트 57개로 확장 |
| 1.0.0 | 2025-12-09 | 초기 버전 - FastAPI 백엔드 API 설계 문서화 |
