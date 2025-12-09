# LLD: Block Agent System

> **버전**: 1.0.0 | **기준 PRD**: PRD_BLOCK_AGENT_SYSTEM v1.0.0 | **작성일**: 2025-12-09

---

## 1. 개요

### 1.1 목적

본 문서는 Block Agent System의 Low-Level Design을 정의합니다. 컨텍스트 격리, 토큰 관리, 장애 격리 패턴을 통해 AI 기반 개발의 정확도와 안정성을 향상시킵니다.

### 1.2 참조 문서

| 문서 | 경로 | 용도 |
|------|------|------|
| PRD | [../PRD_BLOCK_AGENT_SYSTEM.md](../PRD_BLOCK_AGENT_SYSTEM.md) | 요구사항 정의 |
| Architecture | [../architecture/BLOCK_AGENT_SYSTEM.md](../architecture/BLOCK_AGENT_SYSTEM.md) | 아키텍처 설계 |
| LLD INDEX | [./LLD_INDEX.md](./LLD_INDEX.md) | 전체 LLD 인덱스 |

### 1.3 구현 경로

```
src/agents/
├── __init__.py                  # 패키지 루트
├── core/                        # 핵심 인프라
│   ├── agent_context.py         # AgentContext, WorkflowContext
│   ├── agent_result.py          # AgentResult
│   ├── agent_registry.py        # AgentRegistry (싱글톤)
│   ├── base_agent.py            # BaseAgent (추상 클래스)
│   ├── circuit_breaker.py       # CircuitBreaker, Registry
│   ├── event_bus.py             # EventBus (Pub/Sub)
│   └── exceptions.py            # 커스텀 예외
├── orchestrator/                # 중앙 조율자
│   ├── orchestrator_agent.py    # OrchestratorAgent
│   └── workflow_parser.py       # YAML 파서
├── blocks/                      # 블럭 에이전트
│   ├── parser/parser_agent.py
│   ├── sync/sync_agent.py
│   ├── storage/storage_agent.py
│   ├── query/query_agent.py
│   ├── validation/validation_agent.py
│   └── export/export_agent.py
└── workflows/                   # 워크플로우 정의
    ├── nas_sync.yaml
    ├── full_validation.yaml
    └── export_catalog.yaml
```

---

## 2. Core 모듈 상세

### 2.1 BaseAgent (`src/agents/core/base_agent.py`)

모든 블럭 에이전트의 추상 기본 클래스입니다.

```python
class BaseAgent(ABC):
    """
    핵심 메서드:
    - _check_scope(file_path): 파일 접근 범위 검증
    - _track_tokens(tokens): 토큰 사용량 추적
    - _estimate_tokens(content): 토큰 수 추정

    생명주기:
    - pre_execute(context): 실행 전 준비
    - execute(context, input_data): 메인 로직 (추상)
    - post_execute(result): 실행 후 정리
    - handle_error(error, context): 에러 처리
    """
```

**범위 검증 (_check_scope)**:

```python
def _check_scope(self, file_path: str) -> bool:
    """
    1. forbidden_paths 패턴 매칭 → ScopeViolationError
    2. allowed_paths 패턴 매칭 → True
    3. 매칭 없음 → ScopeViolationError
    """
    normalized_path = file_path.replace("\\", "/")

    # 금지 경로 우선 체크
    for pattern in self._forbidden_paths:
        if fnmatch(normalized_path, pattern):
            raise ScopeViolationError(...)

    # 허용 경로 체크
    for pattern in self._allowed_paths:
        if fnmatch(normalized_path, pattern):
            return True

    raise ScopeViolationError(...)
```

**토큰 추정 알고리즘**:

| 문자 타입 | 토큰 비율 | 근거 |
|----------|----------|------|
| ASCII | 4글자/토큰 | GPT 토크나이저 평균 |
| 비ASCII (한글 등) | 2글자/토큰 | 유니코드 토큰화 특성 |

---

### 2.2 AgentContext (`src/agents/core/agent_context.py`)

실행 컨텍스트 데이터 클래스입니다.

```python
@dataclass
class AgentContext:
    task_id: str                          # 태스크 고유 ID
    correlation_id: Optional[str]         # 추적 ID
    workflow_id: Optional[str]            # 워크플로우 ID
    step_id: Optional[str]                # 단계 ID
    timeout_seconds: int = 300            # 타임아웃
    estimated_tokens: Optional[int]       # 예상 토큰
    input_from_previous: Dict[str, Any]   # 이전 단계 출력
    shared_state: Dict[str, Any]          # 공유 상태
```

---

### 2.3 AgentResult (`src/agents/core/agent_result.py`)

실행 결과 데이터 클래스입니다.

```python
@dataclass
class AgentResult:
    success: bool
    data: Any
    errors: List[str]
    warnings: List[str]
    metrics: Dict[str, Any]
    next_actions: List[str]
    tokens_used: int
    error_type: Optional[str]

    @classmethod
    def success_result(cls, data, **kwargs) -> "AgentResult": ...

    @classmethod
    def failure_result(cls, errors, **kwargs) -> "AgentResult": ...
```

---

### 2.4 CircuitBreaker (`src/agents/core/circuit_breaker.py`)

장애 격리 패턴 구현입니다.

**상태 전이 다이어그램**:

```
                    failure_threshold 도달
    ┌──────────┐ ─────────────────────────────▶ ┌──────────┐
    │  CLOSED  │                                 │   OPEN   │
    │ (정상)   │ ◀───────────────────────────── │  (차단)  │
    └──────────┘         복구 성공               └────┬─────┘
         ▲                                            │
         │                                            │ recovery_timeout 경과
         │        복구 성공                           ▼
         └─────────────────────────────────── ┌──────────┐
                                              │HALF_OPEN │
                   복구 실패 ────────────────▶│ (시험)   │
                                              └──────────┘
```

**설정 파라미터**:

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| failure_threshold | 5 | OPEN 전환 실패 횟수 |
| recovery_timeout | 60초 | HALF_OPEN 전환 대기 |
| success_threshold | 2 | CLOSED 복귀 성공 횟수 |

---

### 2.5 EventBus (`src/agents/core/event_bus.py`)

블럭 간 비동기 통신을 지원합니다.

**지원 패턴**:

| 패턴 | 메서드 | 용도 |
|------|--------|------|
| Pub/Sub | `subscribe()`, `publish()` | 이벤트 브로드캐스트 |
| Request-Response | `request()`, `respond()` | 동기적 요청 |
| Pattern Subscribe | `subscribe_pattern("file.*")` | 와일드카드 구독 |

---

## 3. Block Agents 상세

### 3.1 ParserAgent (`src/agents/blocks/parser/parser_agent.py`)

파일명에서 메타데이터를 추출합니다.

**지원 프로젝트 패턴**:

| 프로젝트 | 정규식 | 추출 필드 |
|----------|--------|----------|
| WSOP | `WSOP\s*(\d{4})?\s*Event\s*#?(\d+)?...` | year, event_num, event_name, day, part |
| WPT | `WPT\s*(\d{4})?\s*...Episode\s*(\d+)?` | year, event_name, episode, part |
| GGPK | `(?:GG\s*Poker|GGPK)\s*(\d{4})?...` | year, event_name, part |
| EPT | `EPT\s*(\d{4})?\s*([A-Za-z]+)?...` | year, location, event_name, day |
| APT | `APT\s*(\d{4})?\s*...Day\s*(\d+)?` | year, event_name, day |

**신뢰도 계산**:

```python
confidence = sum([
    0.4 if project_detected else 0,
    0.15 if year_extracted else 0,
    0.1 if event_number_extracted else 0,
    0.1 if event_name_extracted else 0,
    0.1 if stage_detected else 0,
    0.05 if part_extracted else 0,
    0.1 if date_extracted else 0,
])
```

---

### 3.2 SyncAgent (`src/agents/blocks/sync/sync_agent.py`)

파일 시스템 스캔 및 동기화를 담당합니다.

**Capabilities**:

| 액션 | 입력 | 출력 |
|------|------|------|
| scan_nas | path, extensions | files[], total |
| scan_gcs | bucket, prefix | files[], total |
| scan_local | path, extensions | files[], total |
| compare_sources | source_files, target_files | diff (source_only, target_only, modified) |
| generate_sync_plan | diff, strategy | actions[], summary |

---

### 3.3 StorageAgent (`src/agents/blocks/storage/storage_agent.py`)

SQLite 데이터베이스 CRUD를 담당합니다.

**보안 조치**:

| 위협 | 대응 |
|------|------|
| SQL Injection | 파라미터 바인딩, 식별자 sanitize |
| 권한 초과 | ALLOWED_TABLES 화이트리스트 |
| 스키마 변경 | execute_sql은 SELECT만 허용 |

---

### 3.4 QueryAgent (`src/agents/blocks/query/query_agent.py`)

고급 검색 기능을 제공합니다.

**QueryBuilder 패턴**:

```python
builder = QueryBuilder(
    table="video_files",
    columns=["filename", "project"],
    filters=[QueryFilter("project", "eq", "WSOP")],
    order_by=[("year", SortOrder.DESC)],
    limit=100,
)
sql, params = builder.build()
# SELECT filename, project FROM video_files WHERE project = ? ORDER BY year DESC LIMIT 100
```

---

### 3.5 ValidationAgent (`src/agents/blocks/validation/validation_agent.py`)

데이터 무결성을 검증합니다.

**검증 규칙 (video_files)**:

```python
RECORD_SCHEMAS = {
    "video_files": {
        "required": ["filename"],
        "types": {"year": int, "part": int, "size": int},
        "constraints": {
            "year": {"min": 2000, "max": 2030},
            "part": {"min": 1, "max": 100},
        },
        "patterns": {
            "filename": r".+\.(mp4|mkv|avi|mov|wmv|m4v)$",
        },
    }
}
```

---

### 3.6 ExportAgent (`src/agents/blocks/export/export_agent.py`)

다양한 형식으로 데이터를 내보냅니다.

**지원 포맷**:

| 포맷 | 메서드 | 출력 |
|------|--------|------|
| CSV | export_csv | 파일 또는 문자열 |
| JSON | export_json | Pretty/Compact 선택 |
| JSONL | export_jsonl | 스트리밍 처리 가능 |
| Sheets | export_sheets | Google Sheets 업로드 |

---

## 4. Orchestrator 상세

### 4.1 OrchestratorAgent (`src/agents/orchestrator/orchestrator_agent.py`)

워크플로우를 실행하고 블럭을 조율합니다.

**실행 흐름**:

```
execute_workflow(workflow_name, params)
    │
    ├─ 1. workflow = parser.load(workflow_name)
    ├─ 2. wf_context = WorkflowContext(...)
    ├─ 3. hooks.on_start 실행
    │
    ├─ 4. for step in workflow.steps:
    │      ├─ condition 평가
    │      ├─ 변수 해석 (${step_id.output})
    │      ├─ CircuitBreaker 체크
    │      ├─ dispatch(block_id, action, inputs)
    │      └─ on_failure 처리 (abort/skip/rollback/continue)
    │
    ├─ 5. hooks.on_complete 실행
    └─ 6. AgentResult 반환
```

**변수 해석 문법**:

```yaml
inputs:
  filename: "${params.filename}"          # params에서 가져오기
  records: "${parse_step.results}"        # 이전 단계 출력
  count: "${validate_step.errors}"        # 중첩 접근
```

---

### 4.2 WorkflowParser (`src/agents/orchestrator/workflow_parser.py`)

YAML 워크플로우를 파싱합니다.

**워크플로우 스키마**:

```yaml
workflow_id: string       # 고유 ID
name: string              # 표시 이름
version: string           # 버전
description: string       # 설명

context_isolation:
  enabled: bool           # 컨텍스트 격리
  max_tokens_per_step: int

steps:
  - id: string            # 단계 ID
    block_id: string      # 블럭 ID (BLOCK_*)
    action: string        # 실행 액션
    inputs: object        # 입력 (변수 해석 지원)
    outputs: string[]     # 출력 키
    on_failure: abort|skip|rollback|continue
    timeout: int          # 초
    token_budget: int     # 토큰 한도
    parallel: bool        # 병렬 실행
    condition: string     # 조건 표현식

hooks:
  on_start: action[]
  on_complete: action[]
  on_error: action[]
```

---

## 5. 워크플로우 예시

### 5.1 NAS 동기화 (`src/agents/workflows/nas_sync.yaml`)

```yaml
workflow_id: nas_sync
name: NAS 동기화 워크플로우

steps:
  - id: scan_nas
    block_id: BLOCK_SYNC
    action: scan_nas
    inputs:
      path: "${params.nas_path}"
    on_failure: abort

  - id: parse_files
    block_id: BLOCK_PARSER
    action: parse_batch
    inputs:
      filenames: "${scan_nas.files}"
    on_failure: continue

  - id: validate_data
    block_id: BLOCK_VALIDATION
    action: validate_batch
    inputs:
      records: "${parse_files.results}"
    on_failure: continue

  - id: save_records
    block_id: BLOCK_STORAGE
    action: bulk_upsert
    inputs:
      records: "${parse_files.results}"
    on_failure: rollback
    condition: "${validate_data.passed}"
```

---

## 6. 테스트 전략

### 6.1 단위 테스트

| 테스트 파일 | 대상 | 주요 케이스 |
|------------|------|------------|
| test_core.py | Core 모듈 | Context, Result, BaseAgent, Registry, EventBus, CircuitBreaker |
| test_parser_agent.py | ParserAgent | 프로젝트 패턴, 신뢰도 계산, 배치 처리 |
| test_workflow_parser.py | WorkflowParser | YAML 파싱, 유효성 검증, 변수 참조 |

### 6.2 실행 방법

```bash
# 전체 테스트
pytest tests/agents/ -v

# 특정 테스트
pytest tests/agents/test_core.py -v

# 커버리지
pytest tests/agents/ --cov=src/agents --cov-report=term
```

---

## 7. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0.0 | 2025-12-09 | 초기 버전 |

---

**문서 버전**: 1.0.0
**작성일**: 2025-12-09
**상태**: Initial
