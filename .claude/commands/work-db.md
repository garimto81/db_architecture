---
name: work-db
description: GGP Poker Video Catalog DB 프로젝트 전용 작업 커맨드
---

# /work-db - DB Architecture 프로젝트 전용 작업 커맨드

GGP Poker Video Catalog Database 프로젝트에 최적화된 작업 실행 커맨드입니다.
**문서 기반 개발**을 강제하여 PRD → Architecture → LLD → Implementation 인과 관계를 유지합니다.

## 사용법

```bash
/work-db <작업 지시>
/work-db "ParserAgent에 HCL 프로젝트 패턴 추가"
/work-db "ValidationAgent에 파일 해시 검증 기능 추가"
/work-db "NAS 동기화 워크플로우에 알림 단계 추가"
```

## 실행 흐름

```
/work-db 실행
    │
    ├─ Phase 0: 문서 계층 확인 ─────────────────────────────────┐
    │      │                                                    │
    │      ├─ 문서 인과 관계 검증                               │ 필수
    │      │   PRD → Architecture → LLD → Implementation        │
    │      │                                                    │
    │      └─ 영향받는 블럭 식별                                 │
    │         (BLOCK_PARSER, BLOCK_SYNC, BLOCK_STORAGE, etc.)  │
    │                                                    ───────┘
    │
    ├─ Phase 1: 병렬 분석 ─────────────────────────────────────┐
    │      │                                                    │
    │      ├─ [Agent 1] 문서 분석                               │
    │      │   ├─ docs/PRD.md                                   │
    │      │   ├─ docs/PRD_BLOCK_AGENT_SYSTEM.md                │
    │      │   ├─ docs/architecture/BLOCK_AGENT_SYSTEM.md       │
    │      │   └─ docs/lld/*.md                                 │ 병렬
    │      │                                                    │
    │      └─ [Agent 2] 코드 분석                               │
    │          ├─ src/agents/core/                              │
    │          ├─ src/agents/blocks/                            │
    │          └─ src/agents/orchestrator/                      │
    │                                                    ───────┘
    │
    ├─ Phase 2: 블럭 범위 검증
    │      │
    │      ├─ 작업 대상 블럭 확인
    │      ├─ 토큰 예산 확인 (블럭별 30K-50K)
    │      └─ 의존성 그래프 분석
    │
    ├─ Phase 3: TDD 기반 구현
    │      │
    │      ├─ Red: 테스트 먼저 작성
    │      ├─ Green: 구현
    │      └─ Refactor: 리팩토링
    │
    ├─ Phase 4: 문서 동기화
    │      │
    │      ├─ LLD 문서 업데이트 (필요 시)
    │      └─ CHANGELOG.md 추가
    │
    └─ Phase 5: 검증 및 보고
           │
           ├─ 테스트 실행
           ├─ 문서-코드 일관성 검증
           └─ 최종 보고서
```

## Phase 0: 문서 계층 확인 (핵심)

### 문서 인과 관계

```
┌─────────────────────────────────────────────────────────────────────┐
│                        문서 계층 구조                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────┐                                                │
│  │      PRD        │  ← 요구사항 정의                                │
│  │ PRD.md          │                                                │
│  │ PRD_BLOCK_*.md  │                                                │
│  └────────┬────────┘                                                │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────┐                                                │
│  │  Architecture   │  ← 아키텍처 설계                                │
│  │ BLOCK_AGENT_*.md│                                                │
│  └────────┬────────┘                                                │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────┐                                                │
│  │      LLD        │  ← 상세 설계                                    │
│  │ 01_DATABASE_*.md│                                                │
│  │ 02_SYNC_*.md    │                                                │
│  │ 03_FILE_*.md    │                                                │
│  │ 04_DOCKER_*.md  │                                                │
│  │ 05_AGENT_*.md   │  ← Block Agent System                          │
│  └────────┬────────┘                                                │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────┐                                                │
│  │ Implementation  │  ← 구현 코드                                    │
│  │ src/agents/     │                                                │
│  │ tests/agents/   │                                                │
│  └─────────────────┘                                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 영향 블럭 매핑

| 작업 키워드 | 대상 블럭 | 관련 문서 |
|------------|----------|----------|
| Parser, 파싱, 패턴 | BLOCK_PARSER | 03_FILE_PARSER.md, 05_AGENT_SYSTEM.md |
| Sync, 동기화, NAS, GCS | BLOCK_SYNC | 02_SYNC_SYSTEM.md, 05_AGENT_SYSTEM.md |
| Storage, DB, CRUD | BLOCK_STORAGE | 01_DATABASE_SCHEMA.md, 05_AGENT_SYSTEM.md |
| Query, 검색, 필터 | BLOCK_QUERY | 05_AGENT_SYSTEM.md |
| Validation, 검증 | BLOCK_VALIDATION | 05_AGENT_SYSTEM.md |
| Export, 내보내기 | BLOCK_EXPORT | 05_AGENT_SYSTEM.md |
| Orchestrator, 워크플로우 | ORCHESTRATOR | 05_AGENT_SYSTEM.md |

## Phase 1: 병렬 분석

### 문서 분석 에이전트

```python
Task(
    subagent_type="Explore",
    prompt="""
    작업 지시: {instruction}

    다음 DB Architecture 프로젝트 문서를 분석하세요:

    1. PRD 분석
       - docs/PRD.md
       - docs/PRD_BLOCK_AGENT_SYSTEM.md

    2. Architecture 분석
       - docs/architecture/BLOCK_AGENT_SYSTEM.md

    3. LLD 분석
       - docs/lld/LLD_INDEX.md
       - docs/lld/05_AGENT_SYSTEM.md (Block Agent)
       - 관련 LLD 문서 (01~04)

    JSON 형식으로 반환:
    {
        "affected_blocks": ["BLOCK_PARSER", ...],
        "related_docs": [...],
        "prd_requirements": [...],
        "architecture_constraints": [...],
        "lld_specifications": [...]
    }
    """,
    description="문서 분석"
)
```

### 코드 분석 에이전트

```python
Task(
    subagent_type="Explore",
    prompt="""
    작업 지시: {instruction}

    다음 src/agents/ 코드를 분석하세요:

    1. Core 모듈: src/agents/core/
       - base_agent.py
       - exceptions.py
       - circuit_breaker.py

    2. Block Agents: src/agents/blocks/
       - 영향받는 에이전트 식별

    3. Orchestrator: src/agents/orchestrator/
       - workflow_parser.py
       - orchestrator_agent.py

    4. Workflows: src/agents/workflows/
       - 영향받는 워크플로우

    JSON 형식으로 반환:
    {
        "affected_files": [...],
        "dependencies": [...],
        "current_capabilities": [...],
        "modification_points": [...]
    }
    """,
    description="코드 분석"
)
```

## Phase 2: 블럭 범위 검증

### 토큰 예산

| 블럭 | 최대 파일 | 최대 토큰 |
|------|----------|----------|
| BLOCK_PARSER | 25개 | 40K |
| BLOCK_SYNC | 30개 | 50K |
| BLOCK_STORAGE | 35개 | 55K |
| BLOCK_QUERY | 25개 | 40K |
| BLOCK_VALIDATION | 20개 | 35K |
| BLOCK_EXPORT | 15개 | 30K |

### 범위 위반 체크

```python
# 작업 전 검증
if target_block != "BLOCK_PARSER":
    raise ScopeViolationError("Parser 작업인데 다른 블럭 접근 시도")

# 토큰 예산 체크
if estimated_tokens > 40000:  # BLOCK_PARSER 한도
    warn("토큰 예산 초과 가능성, 작업 분할 권장")
```

## Phase 3: TDD 기반 구현

### Red-Green-Refactor

```bash
# 1. Red: 실패하는 테스트 작성
pytest tests/agents/test_parser_agent.py::test_hcl_pattern -v
# FAILED (테스트 없거나 실패)

# 2. Green: 최소 구현
# src/agents/blocks/parser/parser_agent.py 수정

# 3. 테스트 통과 확인
pytest tests/agents/test_parser_agent.py::test_hcl_pattern -v
# PASSED

# 4. Refactor: 리팩토링 (테스트 유지)
```

## Phase 4: 문서 동기화

### 필수 업데이트 대상

| 변경 유형 | 업데이트 문서 |
|----------|--------------|
| 새 패턴 추가 | 03_FILE_PARSER.md |
| 새 기능 추가 | 05_AGENT_SYSTEM.md |
| API 변경 | 해당 블럭 LLD |
| 워크플로우 변경 | 05_AGENT_SYSTEM.md |

### CHANGELOG 형식

```markdown
## [Unreleased]

### Added
- BLOCK_PARSER: HCL 프로젝트 패턴 추가 (#XX)

### Changed
- ...

### Fixed
- ...
```

## Phase 5: 검증 및 보고

### 테스트 실행

```bash
# 영향받는 블럭 테스트만
pytest tests/agents/test_parser_agent.py -v

# 전체 에이전트 테스트
pytest tests/agents/ -v
```

### 최종 보고서

```markdown
# /work-db 작업 완료 보고서

## 작업 요약
- **작업 지시**: {instruction}
- **대상 블럭**: BLOCK_PARSER
- **영향 파일**: 3개

## 문서 참조
- **PRD**: PRD_BLOCK_AGENT_SYSTEM.md §3.1
- **Architecture**: BLOCK_AGENT_SYSTEM.md §2.3
- **LLD**: 05_AGENT_SYSTEM.md §3.1

## 변경 내역
| 파일 | 변경 | 설명 |
|------|------|------|
| parser_agent.py | +25/-0 | HCL 패턴 추가 |
| test_parser_agent.py | +15/-0 | HCL 테스트 추가 |

## 테스트 결과
- 단위 테스트: 45/45 통과
- 커버리지: 87%

## 문서 동기화
- [ ] 03_FILE_PARSER.md 업데이트 완료
- [ ] CHANGELOG.md 추가 완료
```

## 예시

```bash
$ /work-db ParserAgent에 HCL 프로젝트 패턴 추가

📚 Phase 0: 문서 계층 확인
   - PRD_BLOCK_AGENT_SYSTEM.md §3.1: BLOCK_PARSER 정의 확인
   - BLOCK_AGENT_SYSTEM.md: 파서 아키텍처 확인
   - 05_AGENT_SYSTEM.md §3.1: ParserAgent 상세 확인
   ✅ 문서 인과 관계 유효

🔍 Phase 1: 병렬 분석
   [Agent 1] 문서 분석...
      - 영향 블럭: BLOCK_PARSER
      - 관련 문서: 03_FILE_PARSER.md, 05_AGENT_SYSTEM.md
   [Agent 2] 코드 분석...
      - 영향 파일: parser_agent.py
      - 수정 위치: PROJECT_PATTERNS dict

🔒 Phase 2: 블럭 범위 검증
   - 대상 블럭: BLOCK_PARSER
   - 예상 토큰: ~35K (한도 40K)
   ✅ 범위 검증 통과

🧪 Phase 3: TDD 구현
   1. Red: test_hcl_pattern 작성 → FAILED
   2. Green: HCL 패턴 구현 → PASSED
   3. Refactor: 패턴 최적화

📝 Phase 4: 문서 동기화
   - 03_FILE_PARSER.md: HCL 섹션 추가
   - CHANGELOG.md: Added 항목 추가

✅ Phase 5: 검증 완료
   - 테스트: 47/47 통과
   - 문서-코드 일관성: 검증됨

📋 최종 보고서 출력...
```

## 옵션

| 옵션 | 설명 | 예시 |
|------|------|------|
| `--block <name>` | 특정 블럭으로 제한 | `/work-db --block BLOCK_PARSER "패턴 추가"` |
| `--skip-docs` | 문서 동기화 스킵 | `/work-db --skip-docs "긴급 수정"` |
| `--dry-run` | 분석만 (수정 없음) | `/work-db --dry-run "영향 분석"` |

## 연동 커맨드

| 커맨드 | 연동 시점 |
|--------|----------|
| `/tdd` | Phase 3 TDD 구현 |
| `/commit` | 완료 후 커밋 |
| `/create-pr` | PR 생성 |

---

**작업 지시를 입력해 주세요.**
