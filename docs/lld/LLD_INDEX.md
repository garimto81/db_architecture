# LLD: GGP Poker Video Catalog DB

> **버전**: 1.6.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09 | **수정일**: 2025-12-09

---

## 1. 개요

본 문서는 GGP Poker Video Catalog Database 시스템의 Low-Level Design (LLD)을 요약한 인덱스 문서입니다. 각 세부 설계는 별도 문서로 분리되어 있습니다.

### 1.1 문서 구조

```
docs/lld/
├── LLD_INDEX.md           # 본 문서 (요약 및 인덱스)
├── 01_DATABASE_SCHEMA.md  # 데이터베이스 스키마 상세 설계
├── 02_SYNC_SYSTEM.md      # 동기화 시스템 상세 설계
├── 03_FILE_PARSER.md      # 파일명 파서 상세 설계
├── 04_DOCKER_DEPLOYMENT.md # Docker 배포 상세 설계
├── 05_AGENT_SYSTEM.md     # Block Agent System 상세 설계
├── 06_BACKEND_API.md      # Backend REST API 상세 설계
├── 07_CATALOG_SYSTEM.md   # Catalog & Title System 설계
└── 08_FRONTEND_MONITORING.md # Frontend Monitoring Dashboard (NEW)
```

### 1.2 시스템 아키텍처 개요

```
┌────────────────────────────────────────────────────────────────────────┐
│                        GGP POKER VIDEO CATALOG                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐           │
│  │  NAS (SMB)   │     │Google Sheets │     │  pokervod    │           │
│  │ 10.10.100.122│     │  2 Sheets    │     │PostgreSQL 15 │           │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘           │
│         │                    │                    │                    │
│         ▼                    ▼                    ▼                    │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                      SYNC-WORKER (Docker)                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │  │
│  │  │ NAS Scanner │  │Sheets Parser│  │ DB Manager  │              │  │
│  │  │  (mtime)    │  │  (gspread)  │  │ (SQLAlchemy)│              │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │  │
│  │                                                                  │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │  │
│  │  │File Parsers │  │  Scheduler  │  │   Redis     │              │  │
│  │  │ (7 projects)│  │ (1h cycle)  │  │  (Queue)    │              │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 핵심 컴포넌트 요약

### 2.1 데이터베이스 스키마 ([상세](./01_DATABASE_SCHEMA.md))

| 구분 | 테이블 수 | 주요 테이블 |
|------|----------|------------|
| Core | 12개 | Project, Season, Event, Episode, VideoFile, HandClip |
| Sync | 4개 | GoogleSheetSync, NasScanCheckpoint, SyncLog, ChangeHistory |
| **합계** | **16개** | |

**핵심 ERD 요약**:
```
Project ─1:N─▶ Season ─1:N─▶ Event ─1:N─▶ Episode ─1:N─▶ VideoFile
                                              │
                                              ▼
                                          HandClip ◀─N:M─▶ Player
                                              │
                                              ▼
                                          HandClip_Tag ─▶ Tag
```

**주요 Enum**:
| Enum | 값 수 | 예시 |
|------|-------|------|
| Project Code | 7 | WSOP, HCL, GGMILLIONS, MPP, PAD, GOG, OTHER |
| Sub-Category | 6 | ARCHIVE, BRACELET_LV, BRACELET_EU, BRACELET_PARA, CIRCUIT, SUPER_CIRCUIT |
| Version Type | 9 | clean, mastered, stream, subclip, final_edit, nobug, pgm, generic, hires |
| Tag Category | 5 | poker_play, emotion, epic_hand, runout, adjective |

> **참고**: `hand_grade`는 `hand_clips.hand_grade` 컬럼에 직접 저장 (★, ★★, ★★★)

---

### 2.2 동기화 시스템 ([상세](./02_SYNC_SYSTEM.md))

| 기능 | 주기 | 전략 |
|------|------|------|
| NAS 증분 스캔 | 1시간 | mtime 기반 |
| Sheets 동기화 | 1시간 | 행 번호 기반 |
| 전체 검증 | 1일 | 매일 03:00 |
| 주간 정합성 | 1주 | 일요일 04:00 |

**동기화 플로우**:
```
1. Scheduler 트리거 (매 1시간)
2. NAS 스캔 → 신규/수정 파일 감지 → 파일명 파싱 → DB Upsert
3. Sheets 동기화 → 신규 행 감지 → 태그 정규화 → DB Upsert
4. 충돌 해결 (Sheet 우선)
5. SyncLog 기록 → 알림 발송
```

**충돌 해결 정책**:
| 상황 | 정책 |
|------|------|
| 동일 ID, 다른 값 | Sheet 우선 |
| DB에만 존재 | 유지 |
| Sheet에만 존재 | 생성 |
| 양쪽 수정 | conflict 플래그 |

---

### 2.3 파일명 파서 ([상세](./03_FILE_PARSER.md))

7개 프로젝트별 파일명 패턴:

| 프로젝트 | 패턴 예시 | 추출 정보 |
|----------|----------|----------|
| **WSOP Bracelet** | `10-wsop-2024-be-ev-21-25k-nlh-hr-ft-title.mp4` | 번호, 연도, 이벤트, 바이인, 게임, 테이블 |
| **WSOP Circuit** | `WCLA24-15.mp4` | 연도, 클립번호 |
| **GGMillions** | `250507_Super High Roller...with Joey Ingram.mp4` | 날짜, 플레이어 |
| **GOG** | `E01_GOG_final_edit_20231215.mp4` | 에피소드, 버전, 날짜 |
| **PAD** | `PAD S12 E01.mp4` | 시즌, 에피소드 |
| **MPP** | `$1M GTD $1K Mystery Bounty.mp4` | GTD, 바이인, 이벤트 타입 |
| **HCL** | (준비중) | - |

**파서 아키텍처**:
```python
class BaseParser:
    project_code: str
    patterns: List[re.Pattern]

class WSOPBraceletParser(BaseParser):
    # 10-wsop-2024-be-ev-21-25k-nlh-hr-ft-title.mp4

class ParserFactory:
    @staticmethod
    def get_parser(project_code: str) -> BaseParser
```

---

### 2.4 Docker 배포 ([상세](./04_DOCKER_DEPLOYMENT.md))

**컨테이너 구성 (v2.0 Full-Stack)**:
| 컨테이너 | 이미지 | 포트 | 역할 |
|----------|--------|------|------|
| pokervod-db | postgres:15-alpine | 5432 (local) | 메인 DB |
| pokervod-api | python:3.11-slim | 8000 (local) | FastAPI Backend |
| pokervod-frontend | nginx:alpine | 8080 | React SPA + API Proxy |

**아키텍처**:
```
User → :8080 (frontend/nginx) → /api/* → :8000 (api) → :5432 (db)
                              → /ws/*  → WebSocket (api)
                              → /*     → React SPA
```

**볼륨 마운트**:
```
postgres_data → /var/lib/postgresql/data
/z/GGPNAs/ARCHIVE → /nas/ARCHIVE:ro (NAS)
./logs → /app/logs
```

**접속 URL**:
| 서비스 | URL |
|--------|-----|
| Dashboard | http://localhost:8080 |
| API Docs | http://localhost:8080/api/docs |
| WebSocket | ws://localhost:8080/ws/sync |

---

## 3. 데이터 흐름

### 3.1 NAS → DB 흐름

```
NAS (SMB)                    Sync Worker                     PostgreSQL
    │                            │                               │
    │  1. 스캔 요청              │                               │
    │◀─────────────────────────  │                               │
    │                            │                               │
    │  2. 파일 목록 반환         │                               │
    │ ─────────────────────────▶ │                               │
    │   (mtime > checkpoint)     │                               │
    │                            │  3. 체크포인트 조회           │
    │                            │ ─────────────────────────────▶│
    │                            │                               │
    │                            │  4. 파일명 파싱               │
    │                            │  (PatternParser)              │
    │                            │                               │
    │                            │  5. Upsert VideoFile          │
    │                            │ ─────────────────────────────▶│
    │                            │                               │
    │                            │  6. 체크포인트 업데이트        │
    │                            │ ─────────────────────────────▶│
```

### 3.2 Google Sheets → DB 흐름

```
Google Sheets                Sync Worker                     PostgreSQL
    │                            │                               │
    │  1. last_row 조회          │                               │
    │                            │ ─────────────────────────────▶│
    │                            │                               │
    │  2. 신규 행 요청           │                               │
    │◀─────────────────────────  │                               │
    │  (row > last_row)          │                               │
    │                            │                               │
    │  3. 행 데이터 반환         │                               │
    │ ─────────────────────────▶ │                               │
    │                            │                               │
    │                            │  4. 태그 정규화               │
    │                            │  (Tag Normalizer)             │
    │                            │                               │
    │                            │  5. Upsert HandClip           │
    │                            │ ─────────────────────────────▶│
    │                            │                               │
    │                            │  6. 태그/플레이어 연결        │
    │                            │ ─────────────────────────────▶│
```

---

## 4. 기술 스택 요약

| 계층 | 기술 | 버전 |
|------|------|------|
| **Database** | PostgreSQL | 15-alpine |
| **Queue** | Redis | 7-alpine |
| **Runtime** | Python | 3.11 |
| **ORM** | SQLAlchemy | 2.x |
| **Scheduler** | APScheduler | 3.x |
| **Sheets API** | gspread | 5.x |
| **Media** | FFprobe | 6.x |
| **Container** | Docker Compose | 3.8 |

---

## 5. 세부 문서 링크

| 문서 | 설명 | 주요 내용 |
|------|------|----------|
| [01_DATABASE_SCHEMA.md](./01_DATABASE_SCHEMA.md) | DB 스키마 상세 | DDL, 인덱스, 제약조건, 시드 데이터 |
| [02_SYNC_SYSTEM.md](./02_SYNC_SYSTEM.md) | 동기화 시스템 | 스케줄러, 증분 로직, 충돌 해결 |
| [03_FILE_PARSER.md](./03_FILE_PARSER.md) | 파일명 파서 | 7개 프로젝트 파서, 정규식, 테스트 케이스 |
| [04_DOCKER_DEPLOYMENT.md](./04_DOCKER_DEPLOYMENT.md) | Docker 배포 | compose 설정, 볼륨, 운영 명령어 |
| [05_AGENT_SYSTEM.md](./05_AGENT_SYSTEM.md) | Block Agent System | 에이전트 아키텍처, 워크플로우, 구현 |
| [06_BACKEND_API.md](./06_BACKEND_API.md) | Backend REST API | FastAPI, 라우터, 서비스, 스키마 |
| [07_CATALOG_SYSTEM.md](./07_CATALOG_SYSTEM.md) | Catalog & Title System | 카탈로그 구조, 제목 생성, UI 목업 |
| [08_FRONTEND_MONITORING.md](./08_FRONTEND_MONITORING.md) | Frontend Monitoring | React 대시보드, WebSocket, 동기화 모니터링 |

---

### 5.1 Backend API 요약 (신규)

FastAPI 기반 REST API 백엔드 설계입니다.

**API 엔드포인트 (11개):**

| 영역 | 엔드포인트 수 | 설명 |
|------|-------------|------|
| Projects | 3 | 목록, 상세, 통계 |
| Seasons | 1 | 목록 (필터링) |
| Events | 3 | 목록, 상세, 에피소드 |
| Episodes | 1 | 비디오 파일 목록 |
| Health | 3 | DB 상태, 테이블, 연결 |

**계층 구조:**
```
API Routers → Services → Models → PostgreSQL
     ↓
Pydantic Schemas (Request/Response DTO)
```

> **상세**: [06_BACKEND_API.md](./06_BACKEND_API.md)

---

### 5.2 Block Agent System 요약

Block Agent System은 AI 기반 개발의 컨텍스트 격리 및 모듈화를 위한 아키텍처입니다.

**구성 요소:**

| 모듈 | 경로 | 설명 |
|------|------|------|
| Core | `src/agents/core/` | BaseAgent, Registry, EventBus, CircuitBreaker |
| Orchestrator | `src/agents/orchestrator/` | 워크플로우 실행, 블럭 조율 |
| Block Agents | `src/agents/blocks/` | 6개 전담 에이전트 (Parser, Sync, Storage, Query, Validation, Export) |
| Workflows | `src/agents/workflows/` | YAML 워크플로우 정의 |

**핵심 패턴:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                                   │
│  Task Router │ State Manager │ Event Bus │ Circuit Breaker           │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
         ┌───────────┬───────────┼───────────┬───────────┐
         ▼           ▼           ▼           ▼           ▼
   ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
   │  PARSER  ││   SYNC   ││ STORAGE  ││  QUERY   ││  EXPORT  │
   │  Agent   ││  Agent   ││  Agent   ││  Agent   ││  Agent   │
   │ ──────── ││ ──────── ││ ──────── ││ ──────── ││ ──────── │
   │ 25 files ││ 30 files ││ 35 files ││ 25 files ││ 15 files │
   │ 40K tok  ││ 50K tok  ││ 55K tok  ││ 40K tok  ││ 30K tok  │
   └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘
```

> **상세**: [05_AGENT_SYSTEM.md](./05_AGENT_SYSTEM.md) | **PRD**: [PRD_BLOCK_AGENT_SYSTEM.md](../PRD_BLOCK_AGENT_SYSTEM.md)

---

### 5.3 Catalog & Title System 요약 (신규)

넷플릭스 스타일의 카탈로그 시스템으로, 영상 유형에 따른 2가지 구조를 지원합니다.

**영상 유형별 카탈로그 구조:**

| 유형 | 카탈로그 형식 | 제목 형식 |
|------|--------------|----------|
| Full Episode | [대회명] [연도] [이벤트명] | [날짜/세션] |
| Hand Clip | [대회명] [연도] [이벤트명] [날짜] | [플레이어 vs 플레이어] |

**UI 목업:**

```
┌─────────────────────────────────────────────────────────────┐
│ 📂 WSOP 2024 Main Event                        [8 videos]  │
│    ├── Day 1A                                               │
│    ├── Day 1B                                               │
│    └── Final Table                                          │
├─────────────────────────────────────────────────────────────┤
│ 📂 WSOP 2024 Main Event Day 3                 [24 clips]   │
│    ├── Ding vs Boianovsky          [추후 구현]              │
│    └── Aziz vs YINAN               [추후 구현]              │
└─────────────────────────────────────────────────────────────┘
```

**신규 DB 컬럼:**

| 컬럼 | 용도 |
|------|------|
| `content_type` | 콘텐츠 유형 (full_episode, hand_clip) |
| `catalog_title` | 카탈로그 그룹명 |
| `episode_title` | 개별 제목 |
| `ai_description` | AI 추론 설명 [추후 구현] |
| `is_catalog_item` | 대표 파일 여부 |

> **상세**: [07_CATALOG_SYSTEM.md](./07_CATALOG_SYSTEM.md)

---

### 5.4 Frontend Monitoring Dashboard 요약 (신규)

NAS와 Google Sheets 동기화 상태를 실시간 모니터링하는 React 기반 대시보드입니다.

**기술 스택:**

| 계층 | 기술 | 설명 |
|------|------|------|
| Framework | React 18 + TypeScript | SPA 구현 |
| Build | Vite | 빠른 HMR |
| UI | shadcn/ui + Tailwind | 컴포넌트 라이브러리 |
| State | Zustand | 경량 상태 관리 |
| Real-time | WebSocket | 실시간 동기화 이벤트 |
| Data Fetching | TanStack Query | 서버 상태 관리 |

**핵심 기능:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  📊 Dashboard                                                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ 📁 NAS   │  │ 📋 Sheets │  │ 통계     │  │ 로그     │           │
│  │ Sync     │  │ Sync      │  │ Overview │  │ Viewer   │           │
│  │ Status   │  │ Status    │  │          │  │          │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
│                                                                      │
│  [🔄 NAS 동기화]  [🔄 Sheets 동기화]    실시간 WebSocket 연결: ● 연결됨 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**담당 블럭:**

| 블럭 | 책임 | 파일 수 |
|------|------|---------|
| **BLOCK_FRONTEND** | GUI 대시보드 렌더링, 실시간 데이터 표시 | 40개 |

> **상세**: [08_FRONTEND_MONITORING.md](./08_FRONTEND_MONITORING.md)

---

## 6. 참조 문서

| 문서 | 경로 | 용도 |
|------|------|------|
| PRD v5.1 | [../PRD.md](../PRD.md) | 기존 시스템 요구사항 |
| Block Agent PRD | [../PRD_BLOCK_AGENT_SYSTEM.md](../PRD_BLOCK_AGENT_SYSTEM.md) | Agent System 요구사항 |
| Agent Architecture | [../architecture/BLOCK_AGENT_SYSTEM.md](../architecture/BLOCK_AGENT_SYSTEM.md) | 아키텍처 설계 |
| NAS 폴더 구조 | [../NAS_FOLDER_STRUCTURE.md](../NAS_FOLDER_STRUCTURE.md) | 데이터 소스 구조 |
| Google Sheets 분석 | [../GOOGLE_SHEETS_ANALYSIS.md](../GOOGLE_SHEETS_ANALYSIS.md) | 데이터 소스 분석 |

---

**문서 버전**: 1.6.0
**작성일**: 2025-12-09
**수정일**: 2025-12-09
**상태**: Updated - Docker Full-Stack 배포 완료

### 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.6.0 | 2025-12-09 | Docker 배포 v2.0: Full-Stack (Frontend + Backend + DB) 구성 |
| 1.5.0 | 2025-12-09 | Frontend Monitoring LLD (08_FRONTEND_MONITORING.md) 추가, BLOCK_FRONTEND 정의 |
| 1.4.0 | 2025-12-09 | Catalog & Title System LLD (07_CATALOG_SYSTEM.md) 추가, UI 목업 포함 |
| 1.3.0 | 2025-12-09 | Backend API LLD (06_BACKEND_API.md) 추가, 섹션 5.1/5.2 재구성 |
| 1.2.0 | 2025-12-09 | Block Agent System 섹션 추가, 문서 참조 연결 완성 |
| 1.1.0 | 2025-12-09 | #14 제목 형식 일관성, #15 Tag Category 개수 수정 (6→5) |
| 1.0.0 | 2025-12-09 | 초기 버전 |
