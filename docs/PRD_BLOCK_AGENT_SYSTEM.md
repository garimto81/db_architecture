# PRD: Block Agent System for GGP Poker Video Catalog

> **버전**: 1.0.0 | **작성일**: 2025-12-09 | **상태**: Draft

---

## 1. 개요 (Overview)

### 1.1 프로젝트 배경

GGP Poker Video Catalog 시스템의 규모가 커짐에 따라, AI 기반 개발 및 유지보수에서 다음과 같은 문제가 발생합니다:

| 문제 | 현상 | 영향 |
|------|------|------|
| **컨텍스트 오염** | Parser 작업 시 Sync/Storage 코드가 노이즈로 작용 | 환각(Hallucination) 발생 |
| **주의력 분산** | 50개+ 파일 처리 시 AI 집중력 저하 | Lost-in-the-Middle 현상 |
| **에러 전파** | 한 모듈 변경이 전체에 영향 | 디버깅 어려움 |
| **확장성 한계** | 새 기능 추가 시 기존 코드와 충돌 | 개발 속도 저하 |

### 1.2 프로젝트 목표

**Block Agent System** 도입을 통해:

1. **컨텍스트 격리**: 각 블럭이 독립된 컨텍스트에서 작동 (15-30 파일, 30K-50K 토큰)
2. **AI 추론 정확도 향상**: 블럭별 전담 에이전트가 집중적으로 처리
3. **병렬 개발**: 블럭 간 독립성으로 동시 작업 가능
4. **오류 격리**: Circuit Breaker로 장애 전파 방지

### 1.3 성공 지표 (KPIs)

| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|----------|
| AI 코드 생성 정확도 | 70% | 95% | 코드 리뷰 통과율 |
| 평균 작업 완료 시간 | 15분 | 5분 | 태스크별 소요 시간 |
| 에러율 | 15% | 3% | 실패한 작업 비율 |
| 블럭 간 의존성 | N/A | < 3개/블럭 | 의존성 그래프 분석 |

---

## 2. 범위 (Scope)

### 2.1 In Scope

#### 2.1.1 Core Blocks (핵심 블럭)

| 블럭 | 책임 | 파일 수 | 토큰 한도 |
|------|------|---------|----------|
| **BLOCK_PARSER** | 파일명 파싱, 메타데이터 추출 | 25개 | 40K |
| **BLOCK_SYNC** | NAS/Sheets 동기화 | 30개 | 50K |
| **BLOCK_STORAGE** | DB CRUD, 트랜잭션 | 35개 | 55K |
| **BLOCK_QUERY** | 검색, 필터링 | 25개 | 40K |

#### 2.1.2 Support Blocks (지원 블럭)

| 블럭 | 책임 | 파일 수 | 토큰 한도 |
|------|------|---------|----------|
| **BLOCK_VALIDATION** | 데이터 검증 | 20개 | 35K |
| **BLOCK_EXPORT** | 데이터 내보내기 | 15개 | 30K |

#### 2.1.3 Infrastructure (인프라)

| 컴포넌트 | 책임 |
|----------|------|
| **Orchestrator** | 블럭 조율, 워크플로우 실행 |
| **Event Bus** | 블럭 간 비동기 통신 |
| **Agent Registry** | 에이전트 등록/조회 |
| **State Manager** | 전역/워크플로우/블럭 상태 관리 |

### 2.2 Out of Scope

- 실시간 스트리밍 처리
- 사용자 인증/권한 시스템
- 프론트엔드 UI
- 외부 AI 프레임워크 (LangGraph, CrewAI) 통합 - Phase 2 검토

---

## 3. 블럭 정의 (Block Definitions)

### 3.1 BLOCK_PARSER (파서 블럭)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          BLOCK_PARSER                                │
├─────────────────────────────────────────────────────────────────────┤
│  책임: 파일명에서 구조화된 메타데이터 추출                           │
│                                                                      │
│  폴더 구조:                                                          │
│  /blocks/parser/                                                     │
│  ├── .block_rules          # 에이전트 제약조건                       │
│  ├── agents/                                                         │
│  │   └── parser_agent.py   # ParserAgent 구현                        │
│  ├── patterns/                                                       │
│  │   ├── wsop_pattern.py   # WSOP 파일명 패턴                        │
│  │   ├── ggmillions_pattern.py                                       │
│  │   ├── pad_pattern.py                                              │
│  │   ├── gog_pattern.py                                              │
│  │   └── mpp_pattern.py                                              │
│  ├── models/                                                         │
│  │   └── parsed_file.py    # ParsedFile 데이터클래스                 │
│  ├── tools/                                                          │
│  │   ├── regex_engine.py                                             │
│  │   └── ffprobe_wrapper.py                                          │
│  └── tests/                                                          │
│      └── test_patterns.py                                            │
│                                                                      │
│  입력: raw_filename, file_path, project_code                         │
│  출력: ParsedFile, confidence_score, errors                          │
│                                                                      │
│  제약: DB 직접 쓰기 금지, Storage Block 통해서만                      │
└─────────────────────────────────────────────────────────────────────┘
```

**지원 프로젝트 패턴:**

| 프로젝트 | 패턴 예시 | 추출 필드 |
|----------|----------|----------|
| WSOP Bracelet | `10-wsop-2024-be-ev-21-25k-nlh-hr-ft.mp4` | year, event, buy_in, game |
| WSOP Circuit | `WCLA24-15.mp4` | year, clip_number |
| GGMillions | `250507_Super High Roller...with Joey.mp4` | date, featured_player |
| PAD | `PAD S12 E01.mp4` | season, episode |
| GOG | `E01_GOG_final_edit_20231215.mp4` | episode, version, date |
| MPP | `$1M GTD $1K Mystery Bounty.mp4` | gtd, buy_in, event_type |

---

### 3.2 BLOCK_SYNC (동기화 블럭)

```
┌─────────────────────────────────────────────────────────────────────┐
│                           BLOCK_SYNC                                 │
├─────────────────────────────────────────────────────────────────────┤
│  책임: 외부 데이터 소스(NAS, Google Sheets)와 DB 동기화              │
│                                                                      │
│  폴더 구조:                                                          │
│  /blocks/sync/                                                       │
│  ├── .block_rules                                                    │
│  ├── agents/                                                         │
│  │   └── sync_agent.py                                               │
│  ├── connectors/                                                     │
│  │   ├── nas_connector.py      # SMB 프로토콜                        │
│  │   └── sheets_connector.py   # gspread API                         │
│  ├── strategies/                                                     │
│  │   ├── incremental_sync.py   # mtime 기반 증분                     │
│  │   └── full_sync.py          # 전체 동기화                         │
│  ├── models/                                                         │
│  │   ├── sync_result.py                                              │
│  │   └── conflict.py                                                 │
│  └── tests/                                                          │
│                                                                      │
│  입력: source_type, sync_mode, source_config                         │
│  출력: SyncResult, changed_records, conflicts                        │
│                                                                      │
│  의존: BLOCK_PARSER (파일명 파싱), BLOCK_STORAGE (DB 저장)           │
└─────────────────────────────────────────────────────────────────────┘
```

**동기화 주기:**

| 작업 | 주기 | 트리거 |
|------|------|--------|
| NAS 증분 스캔 | 1시간 | Scheduler |
| Sheets 동기화 | 1시간 | Scheduler |
| 전체 검증 | 1일 | 매일 03:00 |
| 정합성 체크 | 1주 | 일요일 04:00 |

---

### 3.3 BLOCK_STORAGE (저장소 블럭)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          BLOCK_STORAGE                               │
├─────────────────────────────────────────────────────────────────────┤
│  책임: 데이터 영속성, CRUD 연산, 트랜잭션 관리                        │
│                                                                      │
│  폴더 구조:                                                          │
│  /blocks/storage/                                                    │
│  ├── .block_rules                                                    │
│  ├── agents/                                                         │
│  │   └── storage_agent.py                                            │
│  ├── repositories/                                                   │
│  │   ├── video_file_repo.py                                          │
│  │   ├── hand_clip_repo.py                                           │
│  │   ├── player_repo.py                                              │
│  │   └── tag_repo.py                                                 │
│  ├── models/                                                         │
│  │   └── entities.py           # SQLAlchemy 모델                     │
│  ├── tools/                                                          │
│  │   ├── transaction_manager.py                                      │
│  │   └── cache_manager.py      # Redis 캐시                          │
│  └── tests/                                                          │
│                                                                      │
│  입력: operation, entity_type, data, options                         │
│  출력: StorageResult, affected_ids, rollback_info                    │
│                                                                      │
│  DB: PostgreSQL 15, Redis 7                                          │
└─────────────────────────────────────────────────────────────────────┘
```

**지원 엔티티:**

| 엔티티 | 테이블 | 주요 연산 |
|--------|--------|----------|
| VideoFile | video_files | CRUD, bulk_upsert |
| HandClip | hand_clips | CRUD, batch_insert |
| Player | players | CRUD, search |
| Tag | tags | CRUD, normalize |
| Season | seasons | CRUD |
| Event | events | CRUD |

---

### 3.4 BLOCK_QUERY (쿼리 블럭)

```
┌─────────────────────────────────────────────────────────────────────┐
│                           BLOCK_QUERY                                │
├─────────────────────────────────────────────────────────────────────┤
│  책임: 복잡한 검색, 필터링, 집계 쿼리 처리                            │
│                                                                      │
│  폴더 구조:                                                          │
│  /blocks/query/                                                      │
│  ├── .block_rules                                                    │
│  ├── agents/                                                         │
│  │   └── query_agent.py                                              │
│  ├── builders/                                                       │
│  │   ├── search_builder.py     # 전문 검색 쿼리                      │
│  │   ├── filter_builder.py     # 동적 필터                           │
│  │   └── aggregate_builder.py  # 집계 쿼리                           │
│  ├── models/                                                         │
│  │   ├── query_criteria.py                                           │
│  │   └── search_result.py                                            │
│  └── tests/                                                          │
│                                                                      │
│  입력: query_type, criteria, pagination                              │
│  출력: results, total_count, facets                                  │
│                                                                      │
│  의존: BLOCK_STORAGE (데이터 조회)                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**쿼리 유형:**

| 유형 | 설명 | 예시 |
|------|------|------|
| **search** | 전문 검색 | "Phil Ivey WSOP 2024" |
| **filter** | 조건 필터링 | project=WSOP, year>=2020 |
| **aggregate** | 집계 통계 | 프로젝트별 파일 수 |
| **faceted** | 다면 검색 | 태그 + 플레이어 + 연도 |

---

### 3.5 BLOCK_VALIDATION (검증 블럭)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BLOCK_VALIDATION                              │
├─────────────────────────────────────────────────────────────────────┤
│  책임: 데이터 무결성 검증, 스키마 검증, 비즈니스 룰 검증              │
│                                                                      │
│  폴더 구조:                                                          │
│  /blocks/validation/                                                 │
│  ├── .block_rules                                                    │
│  ├── agents/                                                         │
│  │   └── validation_agent.py                                         │
│  ├── validators/                                                     │
│  │   ├── schema_validator.py   # JSON Schema 검증                    │
│  │   ├── business_validator.py # 비즈니스 룰                         │
│  │   └── integrity_validator.py # 참조 무결성                        │
│  ├── rules/                                                          │
│  │   ├── video_file_rules.yaml                                       │
│  │   └── hand_clip_rules.yaml                                        │
│  └── tests/                                                          │
│                                                                      │
│  입력: data, schema, validation_level                                │
│  출력: valid_records, invalid_records, validation_errors             │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 3.6 BLOCK_EXPORT (내보내기 블럭)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          BLOCK_EXPORT                                │
├─────────────────────────────────────────────────────────────────────┤
│  책임: 데이터 포맷 변환 및 외부 시스템 내보내기                        │
│                                                                      │
│  폴더 구조:                                                          │
│  /blocks/export/                                                     │
│  ├── .block_rules                                                    │
│  ├── agents/                                                         │
│  │   └── export_agent.py                                             │
│  ├── formatters/                                                     │
│  │   ├── csv_formatter.py                                            │
│  │   ├── json_formatter.py                                           │
│  │   └── xml_formatter.py                                            │
│  ├── exporters/                                                      │
│  │   ├── file_exporter.py                                            │
│  │   └── sheets_exporter.py                                          │
│  └── tests/                                                          │
│                                                                      │
│  입력: data, format, destination                                     │
│  출력: export_path, record_count, export_stats                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. 사용자 스토리 (User Stories)

### 4.1 개발자 관점

#### US-001: 블럭 단위 코드 수정
```
As a 개발자 (지휘자)
I want to Parser 블럭 에이전트에게만 패턴 추가를 지시
So that 다른 블럭에 영향 없이 안전하게 기능을 추가할 수 있다

Acceptance Criteria:
- [ ] Parser 블럭 내 파일만 수정됨
- [ ] 다른 블럭 파일 접근 시 ScopeViolationError 발생
- [ ] 토큰 사용량이 40K 이내
- [ ] 수정 후 Parser 블럭 테스트 통과
```

#### US-002: 워크플로우 실행
```
As a 개발자
I want to NAS 동기화 워크플로우를 실행
So that 새 파일이 자동으로 파싱되어 DB에 저장된다

Acceptance Criteria:
- [ ] Sync → Parser → Validation → Storage 순서로 실행
- [ ] 각 단계의 토큰 사용량이 한도 내
- [ ] 실패 시 해당 블럭만 재시도
- [ ] 전체 결과 리포트 생성
```

#### US-003: 새 블럭 추가
```
As a 개발자
I want to 새로운 Analytics 블럭을 추가
So that 시청 통계 기능을 독립적으로 개발할 수 있다

Acceptance Criteria:
- [ ] /blocks/analytics/ 폴더 구조 생성
- [ ] .block_rules 파일 작성
- [ ] BaseAgent 상속한 AnalyticsAgent 구현
- [ ] AgentRegistry에 등록
- [ ] 기존 블럭과 독립적으로 동작
```

### 4.2 시스템 관점

#### US-004: 컨텍스트 격리
```
As a 시스템
I want to 각 블럭이 격리된 컨텍스트에서 실행
So that 컨텍스트 오염 없이 정확한 AI 추론이 가능하다

Acceptance Criteria:
- [ ] 블럭당 최대 30개 파일
- [ ] 블럭당 최대 50K 토큰
- [ ] 금지된 경로 접근 시 에러
- [ ] 토큰 사용량 추적 및 리포팅
```

#### US-005: 장애 격리
```
As a 시스템
I want to 한 블럭의 장애가 다른 블럭으로 전파되지 않도록
So that 전체 시스템 안정성이 유지된다

Acceptance Criteria:
- [ ] Circuit Breaker 5회 실패 시 open
- [ ] 60초 후 half-open으로 복구 시도
- [ ] 장애 블럭 우회 가능
- [ ] 장애 발생 시 알림
```

---

## 5. 기능 요구사항 (Functional Requirements)

### 5.1 에이전트 시스템

| ID | 요구사항 | 우선순위 | 블럭 |
|----|----------|----------|------|
| FR-001 | BaseAgent 추상 클래스 구현 | P0 | Core |
| FR-002 | 블럭별 전담 에이전트 구현 (6개) | P0 | All |
| FR-003 | AgentRegistry 중앙 관리 | P0 | Core |
| FR-004 | 에이전트 상태 관리 (IDLE/PROCESSING/ERROR) | P1 | Core |
| FR-005 | 토큰 사용량 추적 | P1 | Core |

### 5.2 오케스트레이션

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-010 | Orchestrator 구현 | P0 |
| FR-011 | YAML 기반 워크플로우 정의 | P0 |
| FR-012 | 워크플로우 단계별 실행 | P0 |
| FR-013 | 조건부 분기 지원 | P1 |
| FR-014 | 롤백 메커니즘 | P1 |

### 5.3 블럭 간 통신

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-020 | Event Bus 구현 | P0 |
| FR-021 | 동기 요청-응답 패턴 | P0 |
| FR-022 | 비동기 pub/sub 패턴 | P1 |
| FR-023 | Interface Contract 정의 | P0 |

### 5.4 블럭 규칙

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-030 | .block_rules YAML 파서 | P0 |
| FR-031 | 경로 범위 검증 (_check_scope) | P0 |
| FR-032 | 토큰 한도 검증 | P0 |
| FR-033 | 의존성 선언 및 검증 | P1 |

---

## 6. 비기능 요구사항 (Non-Functional Requirements)

### 6.1 성능

| ID | 요구사항 | 목표 | 측정 방법 |
|----|----------|------|----------|
| NFR-001 | 블럭 응답 시간 | < 5초 (P95) | 에이전트 실행 시간 |
| NFR-002 | 워크플로우 완료 시간 | < 60초 | 전체 워크플로우 |
| NFR-003 | 토큰 효율성 | < 50K/블럭 | 토큰 사용량 모니터링 |

### 6.2 확장성

| ID | 요구사항 | 목표 |
|----|----------|------|
| NFR-010 | 블럭 추가 용이성 | 새 블럭 30분 내 추가 가능 |
| NFR-011 | 수평 확장 | 블럭별 독립 스케일링 |
| NFR-012 | 워크플로우 확장 | YAML만으로 새 워크플로우 정의 |

### 6.3 안정성

| ID | 요구사항 | 목표 |
|----|----------|------|
| NFR-020 | 가용성 | 99.5% uptime |
| NFR-021 | 장애 격리 | 단일 블럭 장애 시 다른 블럭 영향 없음 |
| NFR-022 | 복구 시간 | Circuit Breaker 60초 후 자동 복구 |

### 6.4 관찰 가능성

| ID | 요구사항 | 구현 |
|----|----------|------|
| NFR-030 | 블럭별 메트릭 | Prometheus 포맷 |
| NFR-031 | 분산 추적 | OpenTelemetry |
| NFR-032 | 로깅 | 구조화된 JSON 로그 |
| NFR-033 | 대시보드 | 블럭 상태, 토큰 사용량 시각화 |

---

## 7. 기술 스택

### 7.1 Runtime

| 계층 | 기술 | 버전 | 용도 |
|------|------|------|------|
| Language | Python | 3.11+ | 에이전트 구현 |
| ORM | SQLAlchemy | 2.x | DB 접근 |
| Queue | Redis | 7.x | 작업 큐, 캐시 |
| Database | PostgreSQL | 15 | 메인 저장소 |

### 7.2 Libraries

| 라이브러리 | 용도 | 블럭 |
|-----------|------|------|
| `pydantic` | 데이터 검증 | All |
| `pyyaml` | YAML 파싱 | Core |
| `gspread` | Google Sheets | BLOCK_SYNC |
| `ffmpeg-python` | 미디어 분석 | BLOCK_PARSER |
| `prometheus-client` | 메트릭 | Core |

### 7.3 인프라

| 컴포넌트 | 기술 | 용도 |
|----------|------|------|
| Container | Docker | 배포 |
| Orchestration | Docker Compose | 로컬 개발 |
| File System | SMB (NAS) | 비디오 파일 접근 |

---

## 8. 아키텍처 다이어그램

### 8.1 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  DEVELOPER                                       │
│                            (Conductor - 지휘자)                                  │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATOR                                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │Task Router  │ │State Manager│ │Event Bus    │ │Error Handler│               │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘               │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │
         ┌───────────┬───────────────┼───────────────┬───────────┐
         ▼           ▼               ▼               ▼           ▼
┌─────────────┐┌─────────────┐┌─────────────┐┌─────────────┐┌─────────────┐
│   PARSER    ││    SYNC     ││   STORAGE   ││    QUERY    ││   EXPORT    │
│   BLOCK     ││   BLOCK     ││   BLOCK     ││   BLOCK     ││   BLOCK     │
│ ─────────── ││ ─────────── ││ ─────────── ││ ─────────── ││ ─────────── │
│ ParserAgent ││  SyncAgent  ││StorageAgent ││ QueryAgent  ││ExportAgent  │
│ 25 files    ││  30 files   ││  35 files   ││  25 files   ││  15 files   │
│ 40K tokens  ││  50K tokens ││  55K tokens ││  40K tokens ││  30K tokens │
└──────┬──────┘└──────┬──────┘└──────┬──────┘└──────┬──────┘└──────┬──────┘
       │              │              │              │              │
       ▼              ▼              ▼              ▼              ▼
┌─────────────┐┌─────────────┐┌─────────────┐┌─────────────┐┌─────────────┐
│   Tools     ││   Tools     ││   Tools     ││   Tools     ││   Tools     │
│ - Regex     ││ - SMB       ││ - SQLAlchemy││ - Search    ││ - CSV       │
│ - FFprobe   ││ - gspread   ││ - Redis     ││ - Filter    ││ - JSON      │
└─────────────┘└─────────────┘└──────┬──────┘└─────────────┘└─────────────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │ PostgreSQL  │
                              │   pokervod  │
                              └─────────────┘
```

### 8.2 워크플로우 예시: NAS 동기화

```
┌──────────────────────────────────────────────────────────────────────┐
│                    WF_NAS_SYNC Workflow                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  [1] BLOCK_SYNC          [2] BLOCK_PARSER       [3] BLOCK_VALIDATION │
│  ┌─────────────┐         ┌─────────────┐        ┌─────────────┐      │
│  │ scan_nas    │────────▶│ batch_parse │───────▶│ validate    │      │
│  │             │         │             │        │             │      │
│  │ Output:     │         │ Output:     │        │ Output:     │      │
│  │ new_files[] │         │ parsed[]    │        │ valid[]     │      │
│  └─────────────┘         └─────────────┘        │ invalid[]   │      │
│        │                       │                └──────┬──────┘      │
│        │                       │                       │             │
│        │ on_failure: abort     │ on_failure: skip      │             │
│        │                       │ parallel: true        │             │
│        │                       │                       ▼             │
│        │                       │                [4] BLOCK_STORAGE    │
│        │                       │                ┌─────────────┐      │
│        │                       │                │ bulk_upsert │      │
│        │                       │                │             │      │
│        │                       │                │ Output:     │      │
│        │                       │                │ stored_ids[]│      │
│        │                       │                └─────────────┘      │
│        │                       │                       │             │
│        │                       │                on_failure: rollback │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. 마일스톤 및 로드맵

### Phase 1: Foundation (2주)

| 태스크 | 설명 | 산출물 |
|--------|------|--------|
| T1.1 | 프로젝트 구조 생성 | /blocks/ 폴더 구조 |
| T1.2 | BaseAgent 구현 | agents/base.py |
| T1.3 | .block_rules 파서 구현 | core/block_rules.py |
| T1.4 | AgentRegistry 구현 | core/registry.py |
| T1.5 | 범위 검증 (_check_scope) | core/scope.py |

**완료 기준:**
- [ ] BaseAgent 추상 클래스 동작
- [ ] .block_rules YAML 파싱
- [ ] 범위 위반 시 에러 발생

### Phase 2: Core Blocks (3주)

| 태스크 | 설명 | 산출물 |
|--------|------|--------|
| T2.1 | BLOCK_PARSER 구현 | /blocks/parser/ |
| T2.2 | BLOCK_SYNC 구현 | /blocks/sync/ |
| T2.3 | BLOCK_STORAGE 구현 | /blocks/storage/ |
| T2.4 | BLOCK_QUERY 구현 | /blocks/query/ |
| T2.5 | Interface Contracts 정의 | /shared/contracts/ |

**완료 기준:**
- [ ] 4개 Core Block 독립 동작
- [ ] 블럭 간 계약 기반 통신
- [ ] 각 블럭 단위 테스트 통과

### Phase 3: Orchestration (2주)

| 태스크 | 설명 | 산출물 |
|--------|------|--------|
| T3.1 | Orchestrator 구현 | core/orchestrator.py |
| T3.2 | Event Bus 구현 | core/event_bus.py |
| T3.3 | 워크플로우 파서 | core/workflow.py |
| T3.4 | NAS Sync 워크플로우 | workflows/nas_sync.yaml |
| T3.5 | Sheets Sync 워크플로우 | workflows/sheets_sync.yaml |

**완료 기준:**
- [ ] YAML 워크플로우 실행
- [ ] 블럭 간 데이터 전달
- [ ] 에러 시 롤백

### Phase 4: Support & Polish (2주)

| 태스크 | 설명 | 산출물 |
|--------|------|--------|
| T4.1 | BLOCK_VALIDATION 구현 | /blocks/validation/ |
| T4.2 | BLOCK_EXPORT 구현 | /blocks/export/ |
| T4.3 | Circuit Breaker 구현 | core/circuit_breaker.py |
| T4.4 | 메트릭 및 모니터링 | core/metrics.py |
| T4.5 | 통합 테스트 | tests/integration/ |

**완료 기준:**
- [ ] 6개 전체 블럭 동작
- [ ] Circuit Breaker 장애 격리
- [ ] 대시보드에서 상태 확인

---

## 10. 위험 및 완화

| 위험 | 영향 | 가능성 | 완화 전략 |
|------|------|--------|----------|
| 토큰 한도 초과 | 높음 | 중간 | 블럭 세분화, 동적 한도 조정 |
| 블럭 간 순환 의존 | 높음 | 낮음 | 의존성 그래프 검증, 계층 구조 강제 |
| 성능 병목 | 중간 | 중간 | 병렬 실행, 캐싱, 비동기 처리 |
| 마이그레이션 복잡도 | 중간 | 높음 | 점진적 마이그레이션, 기존 코드 호환 레이어 |

---

## 11. 참조 문서

| 문서 | 설명 |
|------|------|
| [BLOCK_AGENT_SYSTEM.md](./architecture/BLOCK_AGENT_SYSTEM.md) | 아키텍처 상세 설계 |
| [PRD.md](./PRD.md) | 기존 시스템 PRD |
| [LLD_INDEX.md](./lld/LLD_INDEX.md) | Low-Level Design 인덱스 |
| [03_FILE_PARSER.md](./lld/03_FILE_PARSER.md) | 파일 파서 상세 (BLOCK_PARSER 참조) |
| [02_SYNC_SYSTEM.md](./lld/02_SYNC_SYSTEM.md) | 동기화 시스템 (BLOCK_SYNC 참조) |
| [01_DATABASE_SCHEMA.md](./lld/01_DATABASE_SCHEMA.md) | DB 스키마 (BLOCK_STORAGE 참조) |

---

## 12. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0.0 | 2025-12-09 | 초기 버전 |

---

**문서 버전**: 1.0.0
**작성일**: 2025-12-09
**상태**: Draft
**담당**: AI Architect
