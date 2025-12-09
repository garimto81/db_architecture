# LLD: GGP Poker Video Catalog DB

> **버전**: 1.1.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09 | **수정일**: 2025-12-09

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
└── 05_AGENT_DESIGN.md     # 에이전트 시스템 상세 설계 ⭐ NEW
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

**컨테이너 구성**:
| 컨테이너 | 이미지 | 포트 | 역할 |
|----------|--------|------|------|
| pokervod-db | postgres:15-alpine | 5432 | 메인 DB |
| pokervod-redis | redis:7-alpine | 6379 | 작업 큐 |
| pokervod-sync | python:3.11-slim | - | 동기화 워커 |

**볼륨 마운트**:
```
postgres_data → /var/lib/postgresql/data
redis_data → /data
/mnt/nas → /nas:ro (SMB 마운트)
./config → /app/config:ro
./logs → /app/logs
```

**환경 변수**:
| 변수 | 기본값 | 설명 |
|------|--------|------|
| DB_USER | pokervod | DB 사용자 |
| DB_PASSWORD | (필수) | DB 비밀번호 |
| SYNC_INTERVAL_HOURS | 1 | 동기화 주기 (시간) |
| NAS_MOUNT_PATH | /nas | NAS 마운트 경로 |
| SPREADSHEET_ID | (필수) | Google Sheet ID |

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
| [05_AGENT_DESIGN.md](./05_AGENT_DESIGN.md) | 에이전트 시스템 | BaseAgent, Orchestrator, 6개 블럭 에이전트 |

---

## 6. 참조 문서

| 문서 | 경로 |
|------|------|
| PRD v5.1 | [../PRD.md](../PRD.md) |
| NAS 폴더 구조 | [../NAS_FOLDER_STRUCTURE.md](../NAS_FOLDER_STRUCTURE.md) |
| Google Sheets 분석 | [../GOOGLE_SHEETS_ANALYSIS.md](../GOOGLE_SHEETS_ANALYSIS.md) |

---

**문서 버전**: 1.1.0
**작성일**: 2025-12-09
**수정일**: 2025-12-09
**상태**: Updated - Style/Documentation fixes

### 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.2.0 | 2025-12-09 | 05_AGENT_DESIGN.md 추가 - 에이전트 시스템 상세 설계 |
| 1.1.0 | 2025-12-09 | #14 제목 형식 일관성, #15 Tag Category 개수 수정 (6→5) |
| 1.0.0 | 2025-12-09 | 초기 버전 |
