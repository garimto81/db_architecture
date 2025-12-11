# PRD: Database Architecture v2.0

## Schema-Driven Development with Single Source of Truth

> **버전**: 2.0.0 | **작성일**: 2025-12-11 | **상태**: Draft

---

## 1. Executive Summary

### 1.1 문제 정의

현재 db_architecture 프로젝트는 **이중 스키마 관리** 문제로 인해 치명적인 버그가 발생했습니다:

| 문제 | 현황 | 영향 |
|------|------|------|
| init.sql과 ORM 모델 분리 | 9개 테이블 중 5개만 ORM 모델화 (56%) | 스키마 불일치 버그 |
| 마이그레이션 시스템 부재 | Alembic 미설치 | 스키마 변경 추적 불가 |
| Raw SQL 남용 | API의 30%가 Raw SQL 사용 | 타입 안전성 부재 |
| 검증 시스템 부재 | 스키마 변경 시 자동 검증 없음 | 런타임 오류 |

### 1.2 목표

**"ORM 모델 = Single Source of Truth"** 패턴으로 전환하여:

1. 100% ORM 모델 커버리지 달성
2. Alembic 마이그레이션 시스템 도입
3. Raw SQL 완전 제거
4. 스키마 변경 자동 검증 체계 구축

### 1.3 핵심 원칙

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEW ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   SQLAlchemy ORM Models (Single Source of Truth)                │
│   ┌─────────────────────────────────────────────────────┐       │
│   │ • 모든 테이블 100% ORM 모델화                         │       │
│   │ • SQLAlchemy 2.0 Mapped + mapped_column 패턴         │       │
│   │ • 타입 힌트 완전 지원 (Mapped[T])                     │       │
│   │ • Relationships + Back Populates 완성               │       │
│   └───────────────────────┬─────────────────────────────┘       │
│                           │                                      │
│           ┌───────────────┼───────────────┐                     │
│           ▼               ▼               ▼                     │
│   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│   │  Alembic    │ │  API Layer  │ │   Tests     │              │
│   │ Migrations  │ │  (ORM Only) │ │ (Fixtures)  │              │
│   │ ─────────── │ │ ─────────── │ │ ─────────── │              │
│   │ autogenerate│ │ No Raw SQL  │ │ Factory Boy │              │
│   └─────────────┘ └─────────────┘ └─────────────┘              │
│         │                                                        │
│         ▼                                                        │
│   PostgreSQL (자동 동기화)                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Technical Specification

### 2.1 Technology Stack

| 계층 | 현재 | 목표 | 변경 사항 |
|------|------|------|----------|
| **ORM** | SQLAlchemy 2.x (부분) | SQLAlchemy 2.0+ (완전) | Mapped + mapped_column 패턴 |
| **Migration** | 없음 | Alembic 1.13+ | 신규 도입 |
| **Schema** | init.sql (Primary) | ORM Models (Primary) | 역할 전환 |
| **Validation** | 없음 | Pydantic v2 + 스키마 검증 | 신규 도입 |
| **Testing** | pytest (기본) | pytest + factory_boy | 모델 기반 픽스처 |

### 2.2 SQLAlchemy 2.0 Model Pattern

```python
# 현재 (Legacy Pattern)
from sqlalchemy import Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID, primary_key=True)
    code = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)
```

```python
# 목표 (SQLAlchemy 2.0 Pattern)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
from uuid import UUID
from datetime import datetime
from typing import Optional, List

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
    """Reusable timestamp columns."""
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(default=None)

class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = {"schema": "pokervod"}

    # Primary Key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Columns with full type hints
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships (bidirectional)
    seasons: Mapped[List["Season"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
```

### 2.3 Directory Structure

```
backend/
├── alembic/                          # NEW: Migration system
│   ├── versions/
│   │   ├── 001_initial_schema.py
│   │   ├── 002_add_google_sheets.py
│   │   └── 003_add_nas_inventory.py
│   ├── env.py
│   └── script.py.mako
├── alembic.ini                       # NEW: Alembic config
│
├── src/
│   ├── models/                       # REFACTORED: Complete ORM models
│   │   ├── __init__.py              # Export all models
│   │   ├── base.py                  # DeclarativeBase + Mixins
│   │   ├── project.py               # Project model
│   │   ├── season.py                # Season model
│   │   ├── event.py                 # Event model
│   │   ├── episode.py               # Episode model
│   │   ├── video_file.py            # VideoFile model
│   │   ├── hand_clip.py             # NEW: HandClip model
│   │   ├── google_sheet_sync.py     # NEW: GoogleSheetSync model
│   │   ├── nas_folder.py            # NEW: NASFolder model
│   │   └── nas_file.py              # NEW: NASFile model
│   │
│   ├── services/                     # REFACTORED: ORM-only queries
│   │   ├── hand_clip_service.py     # NEW: HandClip CRUD
│   │   ├── google_sheet_service.py  # REFACTORED: Use ORM
│   │   └── nas_inventory_service.py # REFACTORED: Use ORM
│   │
│   └── api/                          # REFACTORED: No raw SQL
│       └── sync.py                  # Remove all text() calls
│
├── docker/
│   ├── init.sql                     # DEPRECATED: Reference only
│   └── docker-compose.yml           # Add migration step
│
└── tests/
    ├── factories/                    # NEW: Model factories
    │   ├── project_factory.py
    │   ├── hand_clip_factory.py
    │   └── ...
    └── conftest.py                  # Use factories for fixtures
```

---

## 3. Complete Model Definitions

### 3.1 Core Models (Existing - Upgrade to 2.0 Pattern)

| Model | Table | Status | Changes |
|-------|-------|--------|---------|
| Project | projects | Upgrade | Add Mapped types |
| Season | seasons | Upgrade | Add Mapped types |
| Event | events | Upgrade | Add Mapped types |
| Episode | episodes | Upgrade | Add back_populates to HandClip |
| VideoFile | video_files | Upgrade | Add back_populates to HandClip, NASFile |

### 3.2 New Models (Create)

#### 3.2.1 HandClip Model

```python
class HandClip(Base, TimestampMixin):
    """핸드 클립 메타데이터 (Google Sheets 연동)"""
    __tablename__ = "hand_clips"
    __table_args__ = (
        UniqueConstraint("sheet_source", "sheet_row_number"),
        {"schema": "pokervod"}
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign Keys
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

#### 3.2.2 GoogleSheetSync Model

```python
class GoogleSheetSync(Base, TimestampMixin):
    """Google Sheet 동기화 상태 추적"""
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

#### 3.2.3 NASFolder Model

```python
class NASFolder(Base, TimestampMixin):
    """NAS 폴더 구조 (Windows 탐색기 동일)"""
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

#### 3.2.4 NASFile Model

```python
class NASFile(Base, TimestampMixin):
    """NAS 전체 파일 인벤토리"""
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

    # Foreign Keys
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

---

## 4. Migration Strategy

### 4.1 Alembic Setup

```ini
# alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

sqlalchemy.url = driver://user:pass@localhost/dbname

[post_write_hooks]
hooks = black
black.type = console_scripts
black.entrypoint = black
black.options = -q
```

```python
# alembic/env.py
from src.models.base import Base
from src.models import (
    Project, Season, Event, Episode, VideoFile,
    HandClip, GoogleSheetSync, NASFolder, NASFile
)

target_metadata = Base.metadata
```

### 4.2 Initial Migration

```bash
# 현재 DB를 baseline으로 설정
alembic stamp head

# 또는 빈 DB에서 시작
alembic revision --autogenerate -m "initial_schema_v2"
alembic upgrade head
```

### 4.3 Docker Integration

```yaml
# docker-compose.yml
services:
  api:
    command: >
      sh -c "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0"
    depends_on:
      db:
        condition: service_healthy
```

### 4.4 Migration Workflow

```
Developer Workflow:
┌─────────────────────────────────────────────────────────────┐
│ 1. Modify ORM Model (src/models/*.py)                       │
│    ↓                                                         │
│ 2. Generate Migration                                        │
│    $ alembic revision --autogenerate -m "description"        │
│    ↓                                                         │
│ 3. Review Generated Script (alembic/versions/*.py)          │
│    ↓                                                         │
│ 4. Test Migration                                            │
│    $ alembic upgrade head                                    │
│    $ alembic downgrade -1  (rollback test)                   │
│    $ alembic upgrade head                                    │
│    ↓                                                         │
│ 5. Commit: Model + Migration Script                          │
│    ↓                                                         │
│ 6. CI/CD Auto-applies: alembic upgrade head                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Raw SQL Elimination Plan

### 5.1 Current Raw SQL Locations

| File | Lines | Raw SQL Usage | Target |
|------|-------|---------------|--------|
| `api/sync.py` | 996-1006 | GoogleSheetSync SELECT | Use GoogleSheetSync model |
| `api/sync.py` | 1009-1027 | HandClip SELECT | Use HandClip model |
| `api/sync.py` | 1315-1326 | HandClip pagination | Use ORM pagination |
| `api/sync.py` | 1391-1404 | HandClip cursor | Use ORM cursor |
| `api/sync.py` | 1454-1478 | HandClip aggregates | Use ORM func.count() |
| `services/sync_service.py` | 1222-1265 | NASFolder upsert | Use ORM merge() |
| `services/sync_service.py` | 1287-1349 | NASFile upsert | Use ORM merge() |
| `services/google_sheet_service.py` | 321-989 | HandClip CRUD | Use HandClipService |

### 5.2 Replacement Patterns

```python
# BEFORE: Raw SQL
db.execute(text("""
    SELECT id, title, created_at FROM pokervod.hand_clips
    WHERE sheet_source = :source ORDER BY created_at DESC LIMIT :limit
"""), {"source": source, "limit": limit})

# AFTER: ORM Query
stmt = (
    select(HandClip)
    .where(HandClip.sheet_source == source)
    .order_by(HandClip.created_at.desc())
    .limit(limit)
)
result = db.execute(stmt).scalars().all()
```

```python
# BEFORE: Raw SQL Upsert
db.execute(text("SELECT id FROM pokervod.nas_files WHERE file_path = :path"))
# ... if exists: UPDATE, else: INSERT

# AFTER: ORM Merge
nas_file = NASFile(
    file_path=path,
    file_name=name,
    file_size_bytes=size
)
db.merge(nas_file)
db.commit()
```

---

## 6. Testing Strategy

### 6.1 Factory Boy Integration

```python
# tests/factories/hand_clip_factory.py
import factory
from src.models import HandClip

class HandClipFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = HandClip
        sqlalchemy_session_persistence = "commit"

    id = factory.LazyFunction(uuid4)
    sheet_source = "metadata_archive"
    sheet_row_number = factory.Sequence(lambda n: n)
    title = factory.Faker("sentence")
    timecode = "00:15:30"
    hand_grade = factory.Iterator(["", "", ""])
```

### 6.2 Test Examples

```python
# tests/api/test_hand_clips.py
def test_get_hand_clips_cursor(db_session, client):
    # Arrange
    HandClipFactory.create_batch(25, sheet_source="metadata_archive")

    # Act
    response = client.get("/api/sync/hand-clips/cursor?limit=10")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["has_more"] is True
    assert data["next_cursor"] is not None
```

---

## 7. Validation & Safety

### 7.1 Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: check-raw-sql
        name: Check for raw SQL usage
        entry: python scripts/check_raw_sql.py
        language: python
        files: \.py$
        exclude: alembic/
```

```python
# scripts/check_raw_sql.py
"""Detect raw SQL usage in codebase."""
import re
import sys

PATTERNS = [
    r'text\s*\(',
    r'execute\s*\(\s*["\']',
    r'raw\s*\(',
]

def check_file(filepath):
    with open(filepath) as f:
        content = f.read()
        for pattern in PATTERNS:
            if re.search(pattern, content):
                print(f"ERROR: Raw SQL detected in {filepath}")
                return False
    return True
```

### 7.2 Schema Validation Test

```python
# tests/test_schema_sync.py
def test_orm_matches_database(db_session, engine):
    """Ensure ORM models match actual database schema."""
    from sqlalchemy import inspect
    from src.models.base import Base

    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names(schema="pokervod"))
    orm_tables = set(Base.metadata.tables.keys())

    # All DB tables should have ORM models
    assert db_tables == {t.split(".")[-1] for t in orm_tables}
```

---

## 8. Implementation Phases

### Phase 1: Foundation (Day 1-2)

| Task | Files | Effort |
|------|-------|--------|
| Upgrade Base to DeclarativeBase | `models/base.py` | 1h |
| Create 4 missing models | `models/*.py` | 3h |
| Update `__init__.py` exports | `models/__init__.py` | 0.5h |
| Setup Alembic | `alembic/`, `alembic.ini` | 2h |
| Generate initial migration | `alembic/versions/` | 1h |

### Phase 2: Service Layer (Day 3-4)

| Task | Files | Effort |
|------|-------|--------|
| Create HandClipService | `services/hand_clip_service.py` | 2h |
| Refactor GoogleSheetService | `services/google_sheet_service.py` | 3h |
| Create NASInventoryService | `services/nas_inventory_service.py` | 2h |
| Update SyncService | `services/sync_service.py` | 3h |

### Phase 3: API Layer (Day 5-6)

| Task | Files | Effort |
|------|-------|--------|
| Refactor sync.py | `api/sync.py` | 4h |
| Remove all text() calls | All API files | 2h |
| Add validation | `api/sync.py` | 2h |

### Phase 4: Testing & Documentation (Day 7)

| Task | Files | Effort |
|------|-------|--------|
| Create factories | `tests/factories/` | 2h |
| Update tests | `tests/` | 3h |
| Add pre-commit hooks | `.pre-commit-config.yaml` | 1h |
| Update CLAUDE.md | `CLAUDE.md` | 1h |

---

## 9. Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| ORM Model Coverage | 56% (5/9) | 100% (9/9) |
| Raw SQL Usage | 13 locations | 0 locations |
| Migration System | None | Alembic |
| Type Safety | Partial | Full (Mapped[T]) |
| Schema-Code Sync | Manual | Automated |
| Test Coverage | ~70% | ~90% |

---

## 10. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Data loss during migration | Backup before alembic upgrade |
| ORM performance regression | Profile queries, use selectin loading |
| Learning curve | Provide SQLAlchemy 2.0 examples |
| Breaking changes | Run existing tests after each refactor |

---

## 11. References

- [SQLAlchemy 2.0 Migration Guide](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html)
- [Alembic Documentation](https://alembic.sqlalchemy.org/en/latest/)
- [FastAPI SQLAlchemy Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Schema-Driven Development](https://blog.noclocks.dev/schema-driven-development-and-single-source-of-truth-essential-practices-for-modern-developers)
- [Database Schema Design Best Practices](https://www.fivetran.com/blog/database-schema-best-practices)

---

## Appendix A: Comparison Table

| Aspect | Current (v1) | New (v2) |
|--------|--------------|----------|
| Schema Authority | init.sql | ORM Models |
| Migration Tool | None | Alembic |
| Model Style | Column() | Mapped[] + mapped_column() |
| Type Safety | Partial | Full |
| API Queries | ORM + Raw SQL | ORM Only |
| Testing | Basic fixtures | Factory Boy |
| Schema Changes | Manual SQL | Auto-generated |
| Rollback | Impossible | alembic downgrade |

---

**문서 버전**: 2.0.0
**작성일**: 2025-12-11
**상태**: Draft - 사용자 승인 대기

### 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 2.0.0 | 2025-12-11 | 초기 작성 - Schema-Driven Development PRD |
