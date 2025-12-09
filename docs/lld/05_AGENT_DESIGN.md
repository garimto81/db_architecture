# LLD 05: Agent Design

> **버전**: 1.0.0 | **기준 PRD**: Block Agent System v1.0.0 | **작성일**: 2025-12-09

---

## 1. 개요

본 문서는 Block Agent System의 에이전트 상세 설계를 정의합니다.

### 1.1 에이전트 계층 구조

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AGENT HIERARCHY                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Layer 0: Infrastructure                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  AgentRegistry │ StateManager │ EventBus │ CircuitBreaker │ Metrics    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                     │                                            │
│  Layer 1: Orchestration            │                                            │
│  ┌─────────────────────────────────▼───────────────────────────────────────┐    │
│  │                         OrchestratorAgent                                │    │
│  │  - 워크플로우 관리                                                        │    │
│  │  - 블럭 에이전트 조율                                                     │    │
│  │  - 전역 상태 관리                                                         │    │
│  └─────────────────────────────────┬───────────────────────────────────────┘    │
│                                     │                                            │
│  Layer 2: Block Agents             │                                            │
│  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐      │
│  │ Parser   ││  Sync    ││ Storage  ││  Query   ││Validation││ Export   │      │
│  │ Agent    ││  Agent   ││  Agent   ││  Agent   ││  Agent   ││  Agent   │      │
│  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 파일 구조

```
/src/agents/
├── core/                           # Layer 0: Infrastructure
│   ├── __init__.py
│   ├── base_agent.py              # BaseAgent 추상 클래스
│   ├── agent_context.py           # AgentContext 데이터클래스
│   ├── agent_result.py            # AgentResult 데이터클래스
│   ├── agent_registry.py          # AgentRegistry 싱글톤
│   ├── state_manager.py           # StateManager
│   ├── event_bus.py               # EventBus
│   ├── circuit_breaker.py         # CircuitBreaker
│   ├── block_rules_loader.py      # .block_rules YAML 로더
│   └── exceptions.py              # 커스텀 예외들
│
├── orchestrator/                   # Layer 1: Orchestration
│   ├── __init__.py
│   ├── orchestrator_agent.py      # OrchestratorAgent
│   ├── workflow_parser.py         # YAML 워크플로우 파서
│   ├── task_router.py             # 태스크 라우터
│   └── workflow_executor.py       # 워크플로우 실행기
│
├── blocks/                         # Layer 2: Block Agents
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── parser_agent.py        # ParserAgent
│   │   ├── patterns/              # 프로젝트별 패턴
│   │   └── tools/                 # 파싱 도구들
│   ├── sync/
│   │   ├── __init__.py
│   │   ├── sync_agent.py          # SyncAgent
│   │   ├── connectors/            # NAS, Sheets 커넥터
│   │   └── strategies/            # 동기화 전략
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── storage_agent.py       # StorageAgent
│   │   ├── repositories/          # 엔티티별 레포지토리
│   │   └── tools/                 # 트랜잭션, 캐시
│   ├── query/
│   │   ├── __init__.py
│   │   ├── query_agent.py         # QueryAgent
│   │   └── builders/              # 쿼리 빌더들
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── validation_agent.py    # ValidationAgent
│   │   └── validators/            # 검증기들
│   └── export/
│       ├── __init__.py
│       ├── export_agent.py        # ExportAgent
│       └── formatters/            # 포맷터들
│
├── contracts/                      # 블럭 간 계약
│   ├── __init__.py
│   ├── parser_contracts.py
│   ├── sync_contracts.py
│   ├── storage_contracts.py
│   └── common_contracts.py
│
└── workflows/                      # 워크플로우 정의
    ├── nas_sync.yaml
    ├── sheets_sync.yaml
    └── full_validation.yaml
```

---

## 2. Core Infrastructure (Layer 0)

### 2.1 BaseAgent 추상 클래스

```python
# /src/agents/core/base_agent.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
from datetime import datetime
from fnmatch import fnmatch
import yaml
import asyncio
import logging

from .agent_context import AgentContext
from .agent_result import AgentResult
from .exceptions import (
    ScopeViolationError,
    TokenLimitExceededError,
    AgentExecutionError,
    BlockRulesValidationError
)


class AgentState(Enum):
    """에이전트 상태"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    WAITING_DEPENDENCY = "waiting_dependency"
    ERROR = "error"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class BaseAgent(ABC):
    """
    블럭 전담 에이전트 기본 클래스

    모든 블럭 에이전트는 이 클래스를 상속받아 구현합니다.

    핵심 책임:
    - 블럭 규칙(.block_rules) 로드 및 검증
    - 파일 접근 범위 검사 (_check_scope)
    - 토큰 사용량 추적 및 제한
    - 표준화된 실행 생명주기 관리

    Example:
        class ParserAgent(BaseAgent):
            def __init__(self):
                super().__init__("BLOCK_PARSER")

            async def execute(self, context, input_data):
                # 파싱 로직 구현
                pass
    """

    def __init__(self, block_id: str, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            block_id: 블럭 고유 식별자 (예: "BLOCK_PARSER")
            config: 에이전트 설정 (선택사항)
        """
        self.block_id = block_id
        self.config = config or {}
        self.state = AgentState.IDLE
        self.logger = logging.getLogger(f"agent.{block_id}")

        # 내부 상태
        self._tools: Dict[str, Any] = {}
        self._memory: Dict[str, Any] = {}
        self._metrics: Dict[str, float] = {}
        self._tokens_used: int = 0

        # 블럭 규칙 로드
        self._block_rules: Dict[str, Any] = {}
        self._allowed_paths: List[str] = []
        self._forbidden_paths: List[str] = []
        self._token_limit: int = 50000
        self._file_limit: int = 30

        self._load_block_rules()

    # ─────────────────────────────────────────────────────────────────
    # Block Rules Management
    # ─────────────────────────────────────────────────────────────────

    def _load_block_rules(self) -> None:
        """블럭 규칙 파일 로드 및 파싱"""
        block_name = self.block_id.lower().replace("block_", "")
        rules_path = f"/blocks/{block_name}/.block_rules"

        try:
            with open(rules_path, 'r', encoding='utf-8') as f:
                self._block_rules = yaml.safe_load(f)

            # 범위 설정 추출
            scope = self._block_rules.get('scope', {})
            self._allowed_paths = scope.get('allowed_paths', [f"/blocks/{block_name}/**"])
            self._forbidden_paths = scope.get('forbidden_paths', [])

            # 제한 설정 추출
            limits = self._block_rules.get('limits', {})
            self._token_limit = limits.get('max_tokens', 50000)
            self._file_limit = limits.get('max_files', 30)

            self.logger.info(f"Loaded block rules: {rules_path}")

        except FileNotFoundError:
            self.logger.warning(f"Block rules not found: {rules_path}, using defaults")
            self._use_default_rules()
        except yaml.YAMLError as e:
            raise BlockRulesValidationError(f"Invalid YAML in {rules_path}: {e}")

    def _use_default_rules(self) -> None:
        """기본 규칙 적용 (규칙 파일 없을 때)"""
        block_name = self.block_id.lower().replace("block_", "")
        self._allowed_paths = [f"/blocks/{block_name}/**"]
        self._forbidden_paths = ["/config/credentials/**", "/blocks/*/.*"]
        self._token_limit = 50000
        self._file_limit = 30

    @property
    def block_rules(self) -> Dict[str, Any]:
        """블럭 규칙 반환"""
        return self._block_rules

    @property
    def role_description(self) -> str:
        """에이전트 역할 설명 반환"""
        return self._block_rules.get('role', f'{self.block_id} 전담 에이전트')

    # ─────────────────────────────────────────────────────────────────
    # Scope Validation
    # ─────────────────────────────────────────────────────────────────

    def _check_scope(self, file_path: str) -> bool:
        """
        파일 접근 범위 검사

        블럭 규칙에 정의된 allowed_paths와 forbidden_paths를 기반으로
        파일 접근 가능 여부를 검사합니다.

        Args:
            file_path: 검사할 파일 경로

        Returns:
            True if 접근 허용

        Raises:
            ScopeViolationError: 접근 금지된 경로
        """
        # 정규화된 경로
        normalized_path = file_path.replace("\\", "/")

        # 1. 금지 경로 체크 (우선)
        for pattern in self._forbidden_paths:
            if fnmatch(normalized_path, pattern):
                self.logger.warning(f"Scope violation (forbidden): {file_path}")
                raise ScopeViolationError(
                    block_id=self.block_id,
                    attempted_path=file_path,
                    reason=f"Path matches forbidden pattern: {pattern}"
                )

        # 2. 허용 경로 체크
        for pattern in self._allowed_paths:
            if fnmatch(normalized_path, pattern):
                return True

        # 3. 어느 허용 패턴과도 매치되지 않음
        self.logger.warning(f"Scope violation (not allowed): {file_path}")
        raise ScopeViolationError(
            block_id=self.block_id,
            attempted_path=file_path,
            reason=f"Path not in allowed scope. Allowed: {self._allowed_paths}"
        )

    def _check_scope_batch(self, file_paths: List[str]) -> List[str]:
        """
        여러 파일의 접근 범위 일괄 검사

        Returns:
            접근 허용된 파일 경로 목록
        """
        allowed_files = []
        for path in file_paths:
            try:
                self._check_scope(path)
                allowed_files.append(path)
            except ScopeViolationError:
                continue
        return allowed_files

    # ─────────────────────────────────────────────────────────────────
    # Token Management
    # ─────────────────────────────────────────────────────────────────

    def _track_tokens(self, tokens: int) -> None:
        """
        토큰 사용량 추적

        Args:
            tokens: 사용한 토큰 수

        Raises:
            TokenLimitExceededError: 토큰 한도 초과
        """
        self._tokens_used += tokens
        self._metrics['tokens_used'] = self._tokens_used

        if self._tokens_used > self._token_limit:
            raise TokenLimitExceededError(
                block_id=self.block_id,
                used=self._tokens_used,
                limit=self._token_limit
            )

    def _estimate_tokens(self, content: str) -> int:
        """
        문자열의 토큰 수 추정

        간단한 휴리스틱: 4글자당 1토큰 (영문 기준)
        한글은 더 많은 토큰 사용하므로 2글자당 1토큰
        """
        # ASCII vs 비ASCII 분리
        ascii_chars = sum(1 for c in content if ord(c) < 128)
        non_ascii_chars = len(content) - ascii_chars

        return (ascii_chars // 4) + (non_ascii_chars // 2) + 1

    @property
    def tokens_remaining(self) -> int:
        """남은 토큰 수"""
        return max(0, self._token_limit - self._tokens_used)

    @property
    def token_usage_percent(self) -> float:
        """토큰 사용률 (0-100%)"""
        return (self._tokens_used / self._token_limit) * 100

    # ─────────────────────────────────────────────────────────────────
    # Lifecycle Methods
    # ─────────────────────────────────────────────────────────────────

    async def pre_execute(self, context: AgentContext) -> None:
        """
        실행 전 준비 단계

        - 상태 변경
        - 컨텍스트 검증
        - 의존성 체크
        """
        self.state = AgentState.INITIALIZING
        self.logger.info(f"Pre-execute: {context.task_id}")

        # 컨텍스트 검증
        self._validate_context(context)

        # 토큰 리셋 (새 태스크)
        self._tokens_used = 0

        self.state = AgentState.PROCESSING

    def _validate_context(self, context: AgentContext) -> None:
        """컨텍스트 유효성 검증"""
        if not context.task_id:
            raise AgentExecutionError("task_id is required")

        # 예상 토큰이 한도를 초과하는지 체크
        if context.estimated_tokens and context.estimated_tokens > self._token_limit:
            self.logger.warning(
                f"Estimated tokens ({context.estimated_tokens}) exceed limit ({self._token_limit})"
            )

    async def post_execute(self, result: AgentResult) -> None:
        """
        실행 후 정리 단계

        - 메트릭 기록
        - 상태 업데이트
        - 리소스 정리
        """
        self.state = AgentState.COMPLETED if result.success else AgentState.ERROR

        # 메트릭 업데이트
        result.metrics.update({
            'tokens_used': self._tokens_used,
            'token_usage_percent': self.token_usage_percent
        })

        self.logger.info(
            f"Post-execute: success={result.success}, tokens={self._tokens_used}"
        )

    async def handle_error(
        self,
        error: Exception,
        context: AgentContext
    ) -> AgentResult:
        """
        에러 처리

        표준화된 에러 처리 및 AgentResult 생성
        """
        self.state = AgentState.ERROR
        self.logger.error(f"Agent error: {error}", exc_info=True)

        return AgentResult(
            success=False,
            data=None,
            errors=[str(error)],
            metrics=self._metrics.copy(),
            next_actions=["retry", "escalate"],
            tokens_used=self._tokens_used,
            error_type=type(error).__name__
        )

    # ─────────────────────────────────────────────────────────────────
    # Abstract Methods (구현 필수)
    # ─────────────────────────────────────────────────────────────────

    @abstractmethod
    async def execute(
        self,
        context: AgentContext,
        input_data: Any
    ) -> AgentResult:
        """
        메인 실행 로직 (구현 필수)

        각 블럭 에이전트가 자신의 핵심 로직을 구현합니다.

        Args:
            context: 실행 컨텍스트 (task_id, correlation_id 등)
            input_data: 입력 데이터 (블럭별로 다름)

        Returns:
            AgentResult: 실행 결과
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        에이전트 능력 목록 반환 (구현 필수)

        이 에이전트가 수행할 수 있는 작업 목록을 반환합니다.

        Returns:
            능력 목록 (예: ["parse_filename", "extract_metadata"])
        """
        pass

    # ─────────────────────────────────────────────────────────────────
    # Tool Management
    # ─────────────────────────────────────────────────────────────────

    def register_tool(self, name: str, tool: Any) -> None:
        """도구 등록"""
        self._tools[name] = tool
        self.logger.debug(f"Registered tool: {name}")

    def get_tool(self, name: str) -> Any:
        """도구 조회"""
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    @property
    def tools(self) -> Dict[str, Any]:
        """등록된 모든 도구"""
        return self._tools.copy()

    # ─────────────────────────────────────────────────────────────────
    # Memory Management
    # ─────────────────────────────────────────────────────────────────

    def remember(self, key: str, value: Any) -> None:
        """메모리에 저장"""
        self._memory[key] = value

    def recall(self, key: str, default: Any = None) -> Any:
        """메모리에서 조회"""
        return self._memory.get(key, default)

    def forget(self, key: str) -> None:
        """메모리에서 삭제"""
        self._memory.pop(key, None)

    def clear_memory(self) -> None:
        """메모리 전체 삭제"""
        self._memory.clear()

    # ─────────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} block_id={self.block_id} state={self.state.value}>"

    def to_dict(self) -> Dict[str, Any]:
        """에이전트 정보를 딕셔너리로 변환"""
        return {
            "block_id": self.block_id,
            "state": self.state.value,
            "capabilities": self.get_capabilities(),
            "tokens_used": self._tokens_used,
            "token_limit": self._token_limit,
            "metrics": self._metrics.copy()
        }
```

### 2.2 AgentContext 데이터클래스

```python
# /src/agents/core/agent_context.py

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4


@dataclass
class AgentContext:
    """
    에이전트 실행 컨텍스트

    각 에이전트 실행 시 전달되는 컨텍스트 정보입니다.
    워크플로우 추적, 타임아웃 관리, 의존성 데이터 전달에 사용됩니다.

    Attributes:
        task_id: 현재 태스크 고유 ID
        correlation_id: 워크플로우 전체를 추적하는 ID
        parent_task_id: 부모 태스크 ID (있는 경우)
        workflow_id: 소속 워크플로우 ID
        step_id: 워크플로우 내 단계 ID

        timeout_seconds: 실행 타임아웃 (초)
        retry_count: 현재 재시도 횟수
        max_retries: 최대 재시도 횟수

        estimated_tokens: 예상 토큰 사용량
        priority: 우선순위 (0=높음, 9=낮음)

        input_from_previous: 이전 단계의 출력 데이터
        shared_state: 워크플로우 전체 공유 상태
        metadata: 추가 메타데이터
    """

    # 필수 필드
    task_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

    # 워크플로우 관련
    parent_task_id: Optional[str] = None
    workflow_id: Optional[str] = None
    step_id: Optional[str] = None

    # 실행 제어
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3

    # 리소스 추정
    estimated_tokens: Optional[int] = None
    priority: int = 5  # 0-9, 낮을수록 높은 우선순위

    # 데이터 전달
    input_from_previous: Optional[Dict[str, Any]] = None
    shared_state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 타임스탬프
    created_at: datetime = field(default_factory=datetime.utcnow)

    def increment_retry(self) -> bool:
        """
        재시도 횟수 증가

        Returns:
            True if 재시도 가능, False if 최대 횟수 초과
        """
        self.retry_count += 1
        return self.retry_count <= self.max_retries

    def can_retry(self) -> bool:
        """재시도 가능 여부"""
        return self.retry_count < self.max_retries

    def get_previous_output(self, key: str, default: Any = None) -> Any:
        """이전 단계 출력에서 값 조회"""
        if self.input_from_previous is None:
            return default
        return self.input_from_previous.get(key, default)

    def set_shared_state(self, key: str, value: Any) -> None:
        """공유 상태 설정"""
        self.shared_state[key] = value

    def get_shared_state(self, key: str, default: Any = None) -> Any:
        """공유 상태 조회"""
        return self.shared_state.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "parent_task_id": self.parent_task_id,
            "workflow_id": self.workflow_id,
            "step_id": self.step_id,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "priority": self.priority,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class WorkflowContext:
    """
    워크플로우 전체 컨텍스트

    여러 에이전트에 걸친 워크플로우 실행 시 사용됩니다.
    """

    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    workflow_name: str = ""

    # 실행 상태
    current_step: int = 0
    total_steps: int = 0
    status: str = "pending"  # pending, running, completed, failed, cancelled

    # 결과 누적
    step_results: Dict[str, Any] = field(default_factory=dict)
    accumulated_data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    # 타임스탬프
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def start(self) -> None:
        """워크플로우 시작"""
        self.status = "running"
        self.started_at = datetime.utcnow()

    def complete(self, success: bool = True) -> None:
        """워크플로우 완료"""
        self.status = "completed" if success else "failed"
        self.completed_at = datetime.utcnow()

    def save_step_result(self, step_id: str, result: Any) -> None:
        """단계 결과 저장"""
        self.step_results[step_id] = result

    def get_step_result(self, step_id: str) -> Any:
        """단계 결과 조회"""
        return self.step_results.get(step_id)

    @property
    def duration_seconds(self) -> Optional[float]:
        """실행 시간 (초)"""
        if not self.started_at:
            return None
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()
```

### 2.3 AgentResult 데이터클래스

```python
# /src/agents/core/agent_result.py

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class AgentResult:
    """
    에이전트 실행 결과

    모든 에이전트는 이 형식으로 결과를 반환합니다.

    Attributes:
        success: 실행 성공 여부
        data: 실행 결과 데이터
        errors: 발생한 에러 목록
        warnings: 경고 메시지 목록
        metrics: 실행 메트릭 (소요 시간, 처리 건수 등)
        next_actions: 후속 권장 액션 목록
        tokens_used: 사용한 토큰 수
        error_type: 에러 타입 (실패 시)
    """

    success: bool
    data: Any = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    next_actions: List[str] = field(default_factory=list)
    tokens_used: int = 0
    error_type: Optional[str] = None

    # 타임스탬프
    completed_at: datetime = field(default_factory=datetime.utcnow)

    def add_error(self, error: str) -> None:
        """에러 추가"""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str) -> None:
        """경고 추가"""
        self.warnings.append(warning)

    def set_metric(self, name: str, value: float) -> None:
        """메트릭 설정"""
        self.metrics[name] = value

    def suggest_action(self, action: str) -> None:
        """후속 액션 제안"""
        if action not in self.next_actions:
            self.next_actions.append(action)

    @property
    def has_errors(self) -> bool:
        """에러 존재 여부"""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """경고 존재 여부"""
        return len(self.warnings) > 0

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "success": self.success,
            "data": self.data,
            "errors": self.errors,
            "warnings": self.warnings,
            "metrics": self.metrics,
            "next_actions": self.next_actions,
            "tokens_used": self.tokens_used,
            "error_type": self.error_type,
            "completed_at": self.completed_at.isoformat()
        }

    @classmethod
    def success_result(
        cls,
        data: Any,
        metrics: Optional[Dict[str, float]] = None,
        tokens_used: int = 0
    ) -> 'AgentResult':
        """성공 결과 생성 헬퍼"""
        return cls(
            success=True,
            data=data,
            metrics=metrics or {},
            tokens_used=tokens_used
        )

    @classmethod
    def failure_result(
        cls,
        error: str,
        error_type: str = "AgentError",
        tokens_used: int = 0
    ) -> 'AgentResult':
        """실패 결과 생성 헬퍼"""
        return cls(
            success=False,
            errors=[error],
            error_type=error_type,
            tokens_used=tokens_used,
            next_actions=["retry", "manual_review"]
        )
```

### 2.4 AgentRegistry 싱글톤

```python
# /src/agents/core/agent_registry.py

from typing import Dict, List, Optional, Type
from threading import Lock
import logging

from .base_agent import BaseAgent


class AgentRegistry:
    """
    에이전트 중앙 등록소 (싱글톤)

    모든 블럭 에이전트를 등록하고 조회하는 중앙 관리자입니다.

    사용법:
        # 등록
        registry = AgentRegistry()
        registry.register(ParserAgent())

        # 조회
        parser = registry.get_agent("BLOCK_PARSER")

        # 능력으로 조회
        agents = registry.find_by_capability("parse_filename")
    """

    _instance: Optional['AgentRegistry'] = None
    _lock: Lock = Lock()

    def __new__(cls) -> 'AgentRegistry':
        """싱글톤 패턴"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._agents: Dict[str, BaseAgent] = {}
        self._capabilities_index: Dict[str, List[str]] = {}  # capability -> [block_ids]
        self.logger = logging.getLogger("agent.registry")
        self._initialized = True

    def register(self, agent: BaseAgent) -> None:
        """
        에이전트 등록

        Args:
            agent: 등록할 에이전트 인스턴스

        Raises:
            ValueError: 이미 등록된 block_id
        """
        if agent.block_id in self._agents:
            raise ValueError(f"Agent already registered: {agent.block_id}")

        self._agents[agent.block_id] = agent

        # 능력 인덱스 업데이트
        for capability in agent.get_capabilities():
            if capability not in self._capabilities_index:
                self._capabilities_index[capability] = []
            self._capabilities_index[capability].append(agent.block_id)

        self.logger.info(f"Registered agent: {agent.block_id}")

    def unregister(self, block_id: str) -> None:
        """에이전트 등록 해제"""
        if block_id not in self._agents:
            return

        agent = self._agents.pop(block_id)

        # 능력 인덱스에서 제거
        for capability in agent.get_capabilities():
            if capability in self._capabilities_index:
                self._capabilities_index[capability].remove(block_id)

        self.logger.info(f"Unregistered agent: {block_id}")

    def get_agent(self, block_id: str) -> BaseAgent:
        """
        에이전트 조회

        Args:
            block_id: 블럭 ID

        Returns:
            등록된 에이전트

        Raises:
            KeyError: 등록되지 않은 block_id
        """
        if block_id not in self._agents:
            raise KeyError(f"Agent not found: {block_id}")
        return self._agents[block_id]

    def get_agent_safe(self, block_id: str) -> Optional[BaseAgent]:
        """에이전트 조회 (안전 버전, None 반환)"""
        return self._agents.get(block_id)

    def find_by_capability(self, capability: str) -> List[BaseAgent]:
        """
        능력으로 에이전트 검색

        Args:
            capability: 찾을 능력

        Returns:
            해당 능력을 가진 에이전트 목록
        """
        block_ids = self._capabilities_index.get(capability, [])
        return [self._agents[bid] for bid in block_ids]

    def list_agents(self) -> List[str]:
        """등록된 모든 에이전트 ID 목록"""
        return list(self._agents.keys())

    def list_capabilities(self) -> List[str]:
        """등록된 모든 능력 목록"""
        return list(self._capabilities_index.keys())

    def get_agent_info(self, block_id: str) -> Dict:
        """에이전트 상세 정보"""
        agent = self.get_agent(block_id)
        return agent.to_dict()

    def get_all_info(self) -> List[Dict]:
        """모든 에이전트 정보"""
        return [agent.to_dict() for agent in self._agents.values()]

    def clear(self) -> None:
        """모든 에이전트 등록 해제 (테스트용)"""
        self._agents.clear()
        self._capabilities_index.clear()

    def __contains__(self, block_id: str) -> bool:
        return block_id in self._agents

    def __len__(self) -> int:
        return len(self._agents)


# 글로벌 인스턴스 (편의를 위해)
_registry: Optional[AgentRegistry] = None

def get_registry() -> AgentRegistry:
    """글로벌 레지스트리 인스턴스 반환"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
```

---

## 3. OrchestratorAgent (Layer 1)

### 3.1 Orchestrator 설계

```python
# /src/agents/orchestrator/orchestrator_agent.py

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import asyncio
import logging
import yaml

from ..core.base_agent import BaseAgent, AgentState
from ..core.agent_context import AgentContext, WorkflowContext
from ..core.agent_result import AgentResult
from ..core.agent_registry import get_registry
from ..core.event_bus import EventBus, Event
from ..core.circuit_breaker import CircuitBreaker
from .workflow_parser import WorkflowParser, Workflow, WorkflowStep
from .task_router import TaskRouter


@dataclass
class OrchestratorConfig:
    """Orchestrator 설정"""
    max_concurrent_workflows: int = 5
    default_timeout: int = 300
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60


class OrchestratorAgent(BaseAgent):
    """
    중앙 조율 에이전트

    개발자(지휘자)의 명령을 받아 적절한 블럭 에이전트에게
    작업을 분배하고 워크플로우를 관리합니다.

    핵심 책임:
    1. 워크플로우 파싱 및 실행
    2. 블럭 에이전트 선택 및 디스패치
    3. 블럭 간 데이터 전달
    4. 에러 처리 및 롤백
    5. 전역 상태 관리

    Example:
        orchestrator = OrchestratorAgent()

        # 워크플로우 실행
        result = await orchestrator.execute_workflow("nas_sync")

        # 직접 디스패치
        result = await orchestrator.dispatch(
            command="add_pattern",
            target_block="BLOCK_PARSER",
            params={"pattern": "..."}
        )
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        # Orchestrator는 block_rules를 사용하지 않음
        self.block_id = "ORCHESTRATOR"
        self.config = config or OrchestratorConfig()
        self.state = AgentState.IDLE
        self.logger = logging.getLogger("agent.orchestrator")

        # 컴포넌트 초기화
        self.registry = get_registry()
        self.event_bus = EventBus()
        self.router = TaskRouter(self.registry)
        self.workflow_parser = WorkflowParser()

        # Circuit Breakers (블럭별)
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

        # 활성 워크플로우 추적
        self._active_workflows: Dict[str, WorkflowContext] = {}

        # 내부 상태
        self._tools = {}
        self._memory = {}
        self._metrics = {}
        self._tokens_used = 0

    def get_capabilities(self) -> List[str]:
        return [
            "execute_workflow",
            "dispatch_to_block",
            "route_task",
            "manage_state",
            "handle_errors"
        ]

    # ─────────────────────────────────────────────────────────────────
    # 워크플로우 실행
    # ─────────────────────────────────────────────────────────────────

    async def execute_workflow(
        self,
        workflow_name: str,
        params: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        YAML 워크플로우 실행

        Args:
            workflow_name: 워크플로우 이름 (파일명에서 .yaml 제외)
            params: 워크플로우 초기 파라미터

        Returns:
            AgentResult: 전체 워크플로우 실행 결과
        """
        self.logger.info(f"Starting workflow: {workflow_name}")

        # 1. 워크플로우 로드 및 파싱
        try:
            workflow = self.workflow_parser.load(workflow_name)
        except FileNotFoundError:
            return AgentResult.failure_result(
                f"Workflow not found: {workflow_name}",
                error_type="WorkflowNotFoundError"
            )

        # 2. 워크플로우 컨텍스트 생성
        wf_context = WorkflowContext(
            workflow_name=workflow_name,
            total_steps=len(workflow.steps)
        )
        wf_context.start()
        self._active_workflows[wf_context.workflow_id] = wf_context

        # 3. 초기 데이터 설정
        if params:
            wf_context.accumulated_data.update(params)

        # 4. 단계별 실행
        try:
            for i, step in enumerate(workflow.steps):
                wf_context.current_step = i + 1

                # 단계 실행
                step_result = await self._execute_step(
                    step=step,
                    workflow_context=wf_context
                )

                # 결과 저장
                wf_context.save_step_result(step.id, step_result)

                # 출력을 다음 단계 입력으로
                if step_result.success and step_result.data:
                    for output_key in step.outputs:
                        if output_key in step_result.data:
                            wf_context.accumulated_data[f"{step.id}.{output_key}"] = \
                                step_result.data[output_key]

                # 실패 처리
                if not step_result.success:
                    if step.on_failure == "abort":
                        wf_context.errors.append(
                            f"Step {step.id} failed: {step_result.errors}"
                        )
                        wf_context.complete(success=False)
                        return AgentResult.failure_result(
                            f"Workflow aborted at step {step.id}",
                            error_type="WorkflowAbortedError"
                        )
                    elif step.on_failure == "rollback":
                        await self._rollback_workflow(wf_context, step)
                        return AgentResult.failure_result(
                            f"Workflow rolled back at step {step.id}",
                            error_type="WorkflowRollbackError"
                        )
                    # skip: 계속 진행

                # 이벤트 발행
                await self.event_bus.publish(Event(
                    type="workflow.step.completed",
                    source_block=self.block_id,
                    data={
                        "workflow_id": wf_context.workflow_id,
                        "step_id": step.id,
                        "success": step_result.success
                    }
                ))

            # 5. 완료
            wf_context.complete(success=True)

            return AgentResult.success_result(
                data=wf_context.accumulated_data,
                metrics={
                    "total_steps": wf_context.total_steps,
                    "duration_seconds": wf_context.duration_seconds or 0
                }
            )

        except Exception as e:
            wf_context.complete(success=False)
            self.logger.error(f"Workflow error: {e}", exc_info=True)
            return AgentResult.failure_result(str(e))

        finally:
            # 정리
            del self._active_workflows[wf_context.workflow_id]

    async def _execute_step(
        self,
        step: WorkflowStep,
        workflow_context: WorkflowContext
    ) -> AgentResult:
        """
        워크플로우 단계 실행
        """
        self.logger.info(f"Executing step: {step.id} -> {step.block_id}")

        # Circuit Breaker 체크
        cb = self._get_circuit_breaker(step.block_id)
        if not cb.can_execute():
            return AgentResult.failure_result(
                f"Circuit breaker open for {step.block_id}",
                error_type="CircuitBreakerOpenError"
            )

        # 에이전트 조회
        try:
            agent = self.registry.get_agent(step.block_id)
        except KeyError:
            return AgentResult.failure_result(
                f"Agent not found: {step.block_id}",
                error_type="AgentNotFoundError"
            )

        # 컨텍스트 생성
        context = AgentContext(
            workflow_id=workflow_context.workflow_id,
            step_id=step.id,
            timeout_seconds=step.timeout or self.config.default_timeout,
            estimated_tokens=step.token_budget,
            input_from_previous=self._resolve_inputs(step.inputs, workflow_context)
        )

        # 입력 데이터 준비
        input_data = self._resolve_inputs(step.inputs, workflow_context)

        # 실행 (타임아웃 적용)
        try:
            result = await asyncio.wait_for(
                agent.execute(context, input_data),
                timeout=context.timeout_seconds
            )

            if result.success:
                cb.record_success()
            else:
                cb.record_failure()

            return result

        except asyncio.TimeoutError:
            cb.record_failure()
            return AgentResult.failure_result(
                f"Step {step.id} timed out after {context.timeout_seconds}s",
                error_type="TimeoutError"
            )
        except Exception as e:
            cb.record_failure()
            return AgentResult.failure_result(str(e))

    def _resolve_inputs(
        self,
        inputs: Dict[str, Any],
        workflow_context: WorkflowContext
    ) -> Dict[str, Any]:
        """
        입력 값 해석 (변수 치환)

        ${step_id.output_key} 형식의 변수를 실제 값으로 치환
        """
        resolved = {}

        for key, value in inputs.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # 변수 참조
                var_path = value[2:-1]  # ${...} 제거
                resolved[key] = workflow_context.accumulated_data.get(var_path)
            else:
                resolved[key] = value

        return resolved

    def _get_circuit_breaker(self, block_id: str) -> CircuitBreaker:
        """블럭별 Circuit Breaker 조회 또는 생성"""
        if block_id not in self._circuit_breakers:
            self._circuit_breakers[block_id] = CircuitBreaker(
                failure_threshold=self.config.circuit_breaker_threshold,
                recovery_timeout=self.config.circuit_breaker_timeout
            )
        return self._circuit_breakers[block_id]

    async def _rollback_workflow(
        self,
        workflow_context: WorkflowContext,
        failed_step: WorkflowStep
    ) -> None:
        """워크플로우 롤백"""
        self.logger.warning(f"Rolling back workflow: {workflow_context.workflow_id}")

        # 완료된 단계들을 역순으로 롤백
        completed_steps = list(workflow_context.step_results.keys())
        for step_id in reversed(completed_steps):
            if step_id == failed_step.id:
                continue

            # 롤백 이벤트 발행
            await self.event_bus.publish(Event(
                type="workflow.step.rollback",
                source_block=self.block_id,
                data={
                    "workflow_id": workflow_context.workflow_id,
                    "step_id": step_id
                }
            ))

    # ─────────────────────────────────────────────────────────────────
    # 직접 디스패치
    # ─────────────────────────────────────────────────────────────────

    async def dispatch(
        self,
        command: str,
        target_block: str,
        params: Dict[str, Any]
    ) -> AgentResult:
        """
        특정 블럭에 직접 명령 전달

        워크플로우 없이 단일 블럭에 작업을 요청할 때 사용합니다.

        Args:
            command: 명령어 (에이전트의 capability와 매칭)
            target_block: 대상 블럭 ID
            params: 명령 파라미터

        Returns:
            AgentResult: 실행 결과

        Example:
            result = await orchestrator.dispatch(
                command="parse_filename",
                target_block="BLOCK_PARSER",
                params={"filename": "10-wsop-2024-be-ev-21.mp4"}
            )
        """
        self.logger.info(f"Dispatching: {command} -> {target_block}")

        # Circuit Breaker 체크
        cb = self._get_circuit_breaker(target_block)
        if not cb.can_execute():
            return AgentResult.failure_result(
                f"Circuit breaker open for {target_block}",
                error_type="CircuitBreakerOpenError"
            )

        # 에이전트 조회
        try:
            agent = self.registry.get_agent(target_block)
        except KeyError:
            return AgentResult.failure_result(
                f"Agent not found: {target_block}",
                error_type="AgentNotFoundError"
            )

        # 능력 체크
        if command not in agent.get_capabilities():
            return AgentResult.failure_result(
                f"Agent {target_block} does not have capability: {command}",
                error_type="CapabilityNotFoundError"
            )

        # 컨텍스트 생성
        context = AgentContext(
            timeout_seconds=self.config.default_timeout
        )

        # 입력 데이터에 command 포함
        input_data = {
            "command": command,
            **params
        }

        # 실행
        try:
            result = await agent.execute(context, input_data)

            if result.success:
                cb.record_success()
            else:
                cb.record_failure()

            return result

        except Exception as e:
            cb.record_failure()
            return AgentResult.failure_result(str(e))

    async def dispatch_parallel(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[AgentResult]:
        """
        여러 블럭에 병렬 디스패치

        Args:
            tasks: [{"command": str, "target_block": str, "params": dict}, ...]

        Returns:
            각 태스크의 결과 목록
        """
        coroutines = [
            self.dispatch(
                command=task["command"],
                target_block=task["target_block"],
                params=task.get("params", {})
            )
            for task in tasks
        ]

        return await asyncio.gather(*coroutines, return_exceptions=True)

    # ─────────────────────────────────────────────────────────────────
    # 라우팅
    # ─────────────────────────────────────────────────────────────────

    async def route(self, request: str, params: Dict[str, Any]) -> AgentResult:
        """
        자연어 요청을 적절한 블럭으로 라우팅

        Args:
            request: 자연어 요청 (예: "WSOP 파일 파싱해줘")
            params: 추가 파라미터

        Returns:
            AgentResult: 라우팅된 에이전트의 실행 결과
        """
        # 라우터가 적절한 블럭과 명령 결정
        routing = self.router.route(request)

        if routing is None:
            return AgentResult.failure_result(
                f"Could not route request: {request}",
                error_type="RoutingError"
            )

        return await self.dispatch(
            command=routing["command"],
            target_block=routing["block_id"],
            params={**params, **routing.get("inferred_params", {})}
        )

    # ─────────────────────────────────────────────────────────────────
    # BaseAgent 추상 메서드 구현
    # ─────────────────────────────────────────────────────────────────

    async def execute(
        self,
        context: AgentContext,
        input_data: Any
    ) -> AgentResult:
        """
        Orchestrator 메인 실행

        input_data 형식에 따라 워크플로우 실행 또는 디스패치
        """
        if isinstance(input_data, dict):
            if "workflow" in input_data:
                return await self.execute_workflow(
                    input_data["workflow"],
                    input_data.get("params")
                )
            elif "command" in input_data and "target_block" in input_data:
                return await self.dispatch(
                    input_data["command"],
                    input_data["target_block"],
                    input_data.get("params", {})
                )
            elif "request" in input_data:
                return await self.route(
                    input_data["request"],
                    input_data.get("params", {})
                )

        return AgentResult.failure_result(
            "Invalid input format for Orchestrator",
            error_type="InvalidInputError"
        )

    # ─────────────────────────────────────────────────────────────────
    # 상태 조회
    # ─────────────────────────────────────────────────────────────────

    def get_active_workflows(self) -> List[Dict]:
        """활성 워크플로우 목록"""
        return [
            {
                "workflow_id": wf.workflow_id,
                "workflow_name": wf.workflow_name,
                "status": wf.status,
                "current_step": wf.current_step,
                "total_steps": wf.total_steps
            }
            for wf in self._active_workflows.values()
        ]

    def get_circuit_breaker_status(self) -> Dict[str, str]:
        """블럭별 Circuit Breaker 상태"""
        return {
            block_id: cb.state
            for block_id, cb in self._circuit_breakers.items()
        }
```

### 3.2 WorkflowParser

```python
# /src/agents/orchestrator/workflow_parser.py

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import yaml
from pathlib import Path


@dataclass
class WorkflowStep:
    """워크플로우 단계"""
    id: str
    block_id: str
    action: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: List[str] = field(default_factory=list)
    on_failure: str = "abort"  # abort, skip, rollback, continue
    timeout: Optional[int] = None
    token_budget: Optional[int] = None
    parallel: bool = False
    condition: Optional[str] = None


@dataclass
class WorkflowHooks:
    """워크플로우 훅"""
    on_start: List[Dict[str, Any]] = field(default_factory=list)
    on_complete: List[Dict[str, Any]] = field(default_factory=list)
    on_error: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Workflow:
    """파싱된 워크플로우"""
    id: str
    name: str
    version: str
    steps: List[WorkflowStep]
    hooks: WorkflowHooks
    context_isolation: bool = True
    max_tokens_per_step: int = 50000


class WorkflowParser:
    """YAML 워크플로우 파서"""

    WORKFLOWS_DIR = Path("/src/agents/workflows")

    def __init__(self, workflows_dir: Optional[Path] = None):
        self.workflows_dir = workflows_dir or self.WORKFLOWS_DIR

    def load(self, workflow_name: str) -> Workflow:
        """
        워크플로우 파일 로드 및 파싱

        Args:
            workflow_name: 워크플로우 이름 (.yaml 제외)

        Returns:
            파싱된 Workflow 객체
        """
        file_path = self.workflows_dir / f"{workflow_name}.yaml"

        if not file_path.exists():
            raise FileNotFoundError(f"Workflow not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        return self._parse(data)

    def _parse(self, data: Dict[str, Any]) -> Workflow:
        """YAML 데이터를 Workflow 객체로 변환"""

        # 단계 파싱
        steps = []
        for step_data in data.get('steps', []):
            step = WorkflowStep(
                id=step_data['id'],
                block_id=step_data['block_id'],
                action=step_data['action'],
                inputs=step_data.get('inputs', {}),
                outputs=step_data.get('outputs', []),
                on_failure=step_data.get('on_failure', 'abort'),
                timeout=step_data.get('timeout'),
                token_budget=step_data.get('token_budget'),
                parallel=step_data.get('parallel', False),
                condition=step_data.get('condition')
            )
            steps.append(step)

        # 훅 파싱
        hooks_data = data.get('hooks', {})
        hooks = WorkflowHooks(
            on_start=hooks_data.get('on_start', []),
            on_complete=hooks_data.get('on_complete', []),
            on_error=hooks_data.get('on_error', [])
        )

        # 컨텍스트 격리 설정
        context_isolation = data.get('context_isolation', {})

        return Workflow(
            id=data.get('workflow_id', 'unknown'),
            name=data.get('name', 'Unknown Workflow'),
            version=data.get('version', '1.0'),
            steps=steps,
            hooks=hooks,
            context_isolation=context_isolation.get('enabled', True),
            max_tokens_per_step=context_isolation.get('max_tokens_per_step', 50000)
        )

    def validate(self, workflow: Workflow) -> List[str]:
        """워크플로우 유효성 검사"""
        errors = []

        if not workflow.steps:
            errors.append("Workflow has no steps")

        step_ids = set()
        for step in workflow.steps:
            # 중복 ID 체크
            if step.id in step_ids:
                errors.append(f"Duplicate step ID: {step.id}")
            step_ids.add(step.id)

            # 필수 필드 체크
            if not step.block_id:
                errors.append(f"Step {step.id} missing block_id")
            if not step.action:
                errors.append(f"Step {step.id} missing action")

        return errors
```

---

## 4. Block Agents (Layer 2)

### 4.1 ParserAgent

```python
# /src/agents/blocks/parser/parser_agent.py

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import re

from ...core.base_agent import BaseAgent
from ...core.agent_context import AgentContext
from ...core.agent_result import AgentResult
from .patterns import PatternFactory
from .tools.ffprobe_wrapper import FFprobeWrapper


@dataclass
class ParseInput:
    """파서 입력"""
    filename: str
    file_path: Optional[str] = None
    project_code: Optional[str] = None
    extract_media_info: bool = False


@dataclass
class ParsedMetadata:
    """파싱된 메타데이터"""
    project_code: str
    filename: str
    parsed_fields: Dict[str, Any]
    confidence: float
    pattern_used: str
    media_info: Optional[Dict[str, Any]] = None


class ParserAgent(BaseAgent):
    """
    파일명 파싱 전담 에이전트

    책임:
    - 7개 프로젝트별 파일명 패턴 매칭
    - 메타데이터 추출 (연도, 이벤트, 플레이어 등)
    - 미디어 정보 추출 (ffprobe)
    - 파싱 신뢰도 계산

    Scope:
    - /blocks/parser/** (허용)
    - /shared/models/parsed_file.py (읽기)

    제약:
    - DB 직접 쓰기 금지 (→ BLOCK_STORAGE)
    - 외부 API 호출 금지
    """

    def __init__(self):
        super().__init__("BLOCK_PARSER")
        self._init_tools()
        self._load_patterns()

    def _init_tools(self) -> None:
        """도구 초기화"""
        self.register_tool("ffprobe", FFprobeWrapper())
        self.register_tool("pattern_factory", PatternFactory())

    def _load_patterns(self) -> None:
        """프로젝트별 패턴 로드"""
        factory = self.get_tool("pattern_factory")
        self.remember("patterns", {
            "WSOP": factory.get_patterns("WSOP"),
            "GGMILLIONS": factory.get_patterns("GGMILLIONS"),
            "PAD": factory.get_patterns("PAD"),
            "GOG": factory.get_patterns("GOG"),
            "MPP": factory.get_patterns("MPP"),
            "HCL": factory.get_patterns("HCL"),
        })

    def get_capabilities(self) -> List[str]:
        return [
            "parse_filename",
            "detect_project",
            "extract_metadata",
            "batch_parse",
            "get_media_info"
        ]

    async def execute(
        self,
        context: AgentContext,
        input_data: Any
    ) -> AgentResult:
        """메인 실행"""
        await self.pre_execute(context)

        try:
            # 입력 정규화
            if isinstance(input_data, dict):
                command = input_data.get("command", "parse_filename")

                if command == "parse_filename":
                    result = await self._parse_filename(
                        ParseInput(
                            filename=input_data["filename"],
                            file_path=input_data.get("file_path"),
                            project_code=input_data.get("project_code"),
                            extract_media_info=input_data.get("extract_media_info", False)
                        )
                    )
                elif command == "batch_parse":
                    result = await self._batch_parse(input_data["files"])
                elif command == "detect_project":
                    result = self._detect_project(input_data["filename"])
                else:
                    result = AgentResult.failure_result(f"Unknown command: {command}")
            else:
                result = AgentResult.failure_result("Invalid input format")

            await self.post_execute(result)
            return result

        except Exception as e:
            return await self.handle_error(e, context)

    async def _parse_filename(self, input_data: ParseInput) -> AgentResult:
        """단일 파일 파싱"""
        filename = input_data.filename
        self._track_tokens(self._estimate_tokens(filename))

        # 1. 프로젝트 감지
        project_code = input_data.project_code or self._detect_project(filename)
        if not project_code:
            return AgentResult.failure_result(
                f"Could not detect project for: {filename}",
                error_type="ProjectDetectionError"
            )

        # 2. 패턴 매칭
        patterns = self.recall("patterns", {}).get(project_code, [])
        best_match = None
        best_confidence = 0.0
        pattern_used = ""

        for pattern in patterns:
            match_result = pattern.match(filename)
            if match_result and match_result.confidence > best_confidence:
                best_match = match_result.data
                best_confidence = match_result.confidence
                pattern_used = pattern.name

        if not best_match:
            return AgentResult(
                success=True,  # 파싱 시도는 성공
                data=ParsedMetadata(
                    project_code=project_code,
                    filename=filename,
                    parsed_fields={},
                    confidence=0.0,
                    pattern_used="none"
                ),
                warnings=["No matching pattern found"],
                next_actions=["manual_review"],
                tokens_used=self._tokens_used
            )

        # 3. 미디어 정보 추출 (옵션)
        media_info = None
        if input_data.extract_media_info and input_data.file_path:
            try:
                self._check_scope(input_data.file_path)
                ffprobe = self.get_tool("ffprobe")
                media_info = await ffprobe.analyze(input_data.file_path)
                self._track_tokens(self._estimate_tokens(str(media_info)))
            except Exception as e:
                self.logger.warning(f"Failed to get media info: {e}")

        # 4. 결과 반환
        return AgentResult.success_result(
            data=ParsedMetadata(
                project_code=project_code,
                filename=filename,
                parsed_fields=best_match,
                confidence=best_confidence,
                pattern_used=pattern_used,
                media_info=media_info
            ),
            metrics={
                "confidence": best_confidence,
                "patterns_tried": len(patterns)
            },
            tokens_used=self._tokens_used
        )

    async def _batch_parse(self, files: List[Dict]) -> AgentResult:
        """배치 파싱"""
        results = []
        success_count = 0

        for file_info in files:
            parse_input = ParseInput(
                filename=file_info["filename"],
                file_path=file_info.get("file_path"),
                project_code=file_info.get("project_code")
            )

            result = await self._parse_filename(parse_input)
            results.append({
                "filename": file_info["filename"],
                "success": result.success,
                "data": result.data if result.success else None,
                "errors": result.errors
            })

            if result.success:
                success_count += 1

        return AgentResult.success_result(
            data={
                "parsed": results,
                "total": len(files),
                "success_count": success_count
            },
            metrics={
                "success_rate": success_count / len(files) if files else 0
            },
            tokens_used=self._tokens_used
        )

    def _detect_project(self, filename: str) -> Optional[str]:
        """파일명에서 프로젝트 감지"""
        filename_lower = filename.lower()

        # 프로젝트별 키워드 매칭
        project_keywords = {
            "WSOP": ["wsop", "wcla", "wsop-"],
            "GGMILLIONS": ["super high roller", "ggmillions"],
            "PAD": ["pad", "poker after dark"],
            "GOG": ["gog", "game of gold"],
            "MPP": ["mpp", "mediterranean poker"],
            "HCL": ["hcl", "hustler"],
        }

        for project, keywords in project_keywords.items():
            for keyword in keywords:
                if keyword in filename_lower:
                    return project

        return None
```

### 4.2 SyncAgent

```python
# /src/agents/blocks/sync/sync_agent.py

from typing import Any, Dict, List, Literal, Optional
from dataclasses import dataclass
from datetime import datetime

from ...core.base_agent import BaseAgent
from ...core.agent_context import AgentContext
from ...core.agent_result import AgentResult
from .connectors.nas_connector import NASConnector
from .connectors.sheets_connector import SheetsConnector
from .strategies.incremental_sync import IncrementalSyncStrategy


@dataclass
class SyncConfig:
    """동기화 설정"""
    source_type: Literal["nas", "sheet"]
    sync_mode: Literal["full", "incremental"] = "incremental"
    batch_size: int = 100


@dataclass
class SyncResult:
    """동기화 결과"""
    source_type: str
    sync_mode: str
    new_records: int
    updated_records: int
    conflicts: List[Dict]
    checkpoint: Optional[str]


class SyncAgent(BaseAgent):
    """
    동기화 전담 에이전트

    책임:
    - NAS 파일 스캔 (SMB)
    - Google Sheets 동기화 (gspread)
    - 증분 동기화 (mtime/row 기반)
    - 충돌 감지 및 보고

    Scope:
    - /blocks/sync/** (허용)
    - NAS: 읽기 전용 접근
    - Sheets: 읽기 전용 접근

    의존:
    - BLOCK_PARSER: 파일명 파싱
    - BLOCK_STORAGE: DB 저장
    """

    def __init__(self):
        super().__init__("BLOCK_SYNC")
        self._init_connectors()

    def _init_connectors(self) -> None:
        """커넥터 초기화"""
        self.register_tool("nas", NASConnector())
        self.register_tool("sheets", SheetsConnector())
        self.register_tool("sync_strategy", IncrementalSyncStrategy())

    def get_capabilities(self) -> List[str]:
        return [
            "scan_nas",
            "sync_sheets",
            "detect_changes",
            "get_checkpoint",
            "resolve_conflict"
        ]

    async def execute(
        self,
        context: AgentContext,
        input_data: Any
    ) -> AgentResult:
        """메인 실행"""
        await self.pre_execute(context)

        try:
            command = input_data.get("command", "scan_nas")

            if command == "scan_nas":
                result = await self._scan_nas(
                    input_data.get("path", "/"),
                    input_data.get("sync_mode", "incremental")
                )
            elif command == "sync_sheets":
                result = await self._sync_sheets(
                    input_data.get("sheet_id"),
                    input_data.get("sheet_name"),
                    input_data.get("sync_mode", "incremental")
                )
            else:
                result = AgentResult.failure_result(f"Unknown command: {command}")

            await self.post_execute(result)
            return result

        except Exception as e:
            return await self.handle_error(e, context)

    async def _scan_nas(
        self,
        path: str,
        sync_mode: str
    ) -> AgentResult:
        """NAS 스캔"""
        nas = self.get_tool("nas")
        strategy = self.get_tool("sync_strategy")

        # 체크포인트 조회
        checkpoint = strategy.get_checkpoint("nas", path)

        # 파일 스캔
        if sync_mode == "incremental" and checkpoint:
            files = await nas.scan_since(path, checkpoint.last_mtime)
        else:
            files = await nas.scan_all(path)

        self._track_tokens(self._estimate_tokens(str(files)))

        # 체크포인트 업데이트
        new_checkpoint = datetime.utcnow().isoformat()

        return AgentResult.success_result(
            data={
                "files": files,
                "new_count": len(files),
                "checkpoint": new_checkpoint
            },
            metrics={
                "files_found": len(files),
                "sync_mode": sync_mode
            },
            tokens_used=self._tokens_used
        )

    async def _sync_sheets(
        self,
        sheet_id: str,
        sheet_name: str,
        sync_mode: str
    ) -> AgentResult:
        """Google Sheets 동기화"""
        sheets = self.get_tool("sheets")
        strategy = self.get_tool("sync_strategy")

        # 체크포인트 조회
        checkpoint = strategy.get_checkpoint("sheet", f"{sheet_id}/{sheet_name}")
        last_row = checkpoint.last_row if checkpoint else 0

        # 데이터 조회
        if sync_mode == "incremental" and last_row > 0:
            rows = await sheets.get_rows_since(sheet_id, sheet_name, last_row)
        else:
            rows = await sheets.get_all_rows(sheet_id, sheet_name)

        self._track_tokens(self._estimate_tokens(str(rows)))

        # 새 체크포인트
        new_last_row = last_row + len(rows)

        return AgentResult.success_result(
            data={
                "rows": rows,
                "new_count": len(rows),
                "last_row": new_last_row
            },
            metrics={
                "rows_synced": len(rows),
                "sync_mode": sync_mode
            },
            tokens_used=self._tokens_used
        )
```

### 4.3 StorageAgent

```python
# /src/agents/blocks/storage/storage_agent.py

from typing import Any, Dict, List, Literal, Optional, Union
from dataclasses import dataclass
from uuid import UUID

from ...core.base_agent import BaseAgent
from ...core.agent_context import AgentContext
from ...core.agent_result import AgentResult
from .repositories.video_file_repo import VideoFileRepository
from .repositories.hand_clip_repo import HandClipRepository
from .tools.transaction_manager import TransactionManager
from .tools.cache_manager import CacheManager


@dataclass
class StorageOptions:
    """저장 옵션"""
    use_cache: bool = True
    batch_size: int = 100
    upsert: bool = True


class StorageAgent(BaseAgent):
    """
    저장소 전담 에이전트

    책임:
    - CRUD 연산
    - 트랜잭션 관리
    - 캐시 관리 (Redis)
    - Bulk 연산

    Scope:
    - /blocks/storage/** (허용)
    - PostgreSQL: 전체 접근
    - Redis: 캐시용 접근
    """

    def __init__(self):
        super().__init__("BLOCK_STORAGE")
        self._init_repositories()

    def _init_repositories(self) -> None:
        """레포지토리 초기화"""
        self.register_tool("tx_manager", TransactionManager())
        self.register_tool("cache", CacheManager())

        # 엔티티별 레포지토리
        self.remember("repositories", {
            "video_file": VideoFileRepository(),
            "hand_clip": HandClipRepository(),
        })

    def get_capabilities(self) -> List[str]:
        return [
            "create",
            "read",
            "update",
            "delete",
            "bulk_upsert",
            "query",
            "transaction"
        ]

    async def execute(
        self,
        context: AgentContext,
        input_data: Any
    ) -> AgentResult:
        """메인 실행"""
        await self.pre_execute(context)

        try:
            command = input_data.get("command", "query")
            entity_type = input_data.get("entity_type")

            repo = self._get_repository(entity_type)
            if not repo:
                return AgentResult.failure_result(
                    f"Unknown entity type: {entity_type}"
                )

            if command == "create":
                result = await self._create(repo, input_data["data"])
            elif command == "read":
                result = await self._read(repo, input_data["id"])
            elif command == "update":
                result = await self._update(repo, input_data["id"], input_data["data"])
            elif command == "delete":
                result = await self._delete(repo, input_data["id"])
            elif command == "bulk_upsert":
                result = await self._bulk_upsert(
                    repo,
                    input_data["data"],
                    StorageOptions(**input_data.get("options", {}))
                )
            elif command == "query":
                result = await self._query(repo, input_data.get("criteria", {}))
            else:
                result = AgentResult.failure_result(f"Unknown command: {command}")

            await self.post_execute(result)
            return result

        except Exception as e:
            return await self.handle_error(e, context)

    def _get_repository(self, entity_type: str):
        """엔티티 타입에 해당하는 레포지토리 반환"""
        repositories = self.recall("repositories", {})
        return repositories.get(entity_type)

    async def _create(self, repo, data: Dict) -> AgentResult:
        """생성"""
        tx_manager = self.get_tool("tx_manager")

        async with tx_manager.transaction():
            entity = await repo.create(data)

        self._track_tokens(self._estimate_tokens(str(data)))

        return AgentResult.success_result(
            data={"id": entity.id, "created": True},
            tokens_used=self._tokens_used
        )

    async def _read(self, repo, entity_id: str) -> AgentResult:
        """조회"""
        cache = self.get_tool("cache")

        # 캐시 체크
        cached = await cache.get(f"{repo.entity_name}:{entity_id}")
        if cached:
            return AgentResult.success_result(data=cached, tokens_used=0)

        # DB 조회
        entity = await repo.get_by_id(entity_id)
        if not entity:
            return AgentResult.failure_result(f"Entity not found: {entity_id}")

        # 캐시 저장
        await cache.set(f"{repo.entity_name}:{entity_id}", entity.to_dict())

        return AgentResult.success_result(
            data=entity.to_dict(),
            tokens_used=self._tokens_used
        )

    async def _update(self, repo, entity_id: str, data: Dict) -> AgentResult:
        """수정"""
        tx_manager = self.get_tool("tx_manager")
        cache = self.get_tool("cache")

        async with tx_manager.transaction():
            entity = await repo.update(entity_id, data)

        # 캐시 무효화
        await cache.delete(f"{repo.entity_name}:{entity_id}")

        self._track_tokens(self._estimate_tokens(str(data)))

        return AgentResult.success_result(
            data={"id": entity_id, "updated": True},
            tokens_used=self._tokens_used
        )

    async def _delete(self, repo, entity_id: str) -> AgentResult:
        """삭제"""
        tx_manager = self.get_tool("tx_manager")
        cache = self.get_tool("cache")

        async with tx_manager.transaction():
            await repo.delete(entity_id)

        # 캐시 무효화
        await cache.delete(f"{repo.entity_name}:{entity_id}")

        return AgentResult.success_result(
            data={"id": entity_id, "deleted": True},
            tokens_used=self._tokens_used
        )

    async def _bulk_upsert(
        self,
        repo,
        data: List[Dict],
        options: StorageOptions
    ) -> AgentResult:
        """대량 Upsert"""
        tx_manager = self.get_tool("tx_manager")

        inserted = 0
        updated = 0
        failed = []

        # 배치 처리
        for i in range(0, len(data), options.batch_size):
            batch = data[i:i + options.batch_size]

            async with tx_manager.transaction():
                for item in batch:
                    try:
                        result = await repo.upsert(item)
                        if result.was_insert:
                            inserted += 1
                        else:
                            updated += 1
                    except Exception as e:
                        failed.append({"data": item, "error": str(e)})

        self._track_tokens(self._estimate_tokens(str(data)))

        return AgentResult.success_result(
            data={
                "inserted": inserted,
                "updated": updated,
                "failed": failed,
                "total": len(data)
            },
            metrics={
                "success_rate": (inserted + updated) / len(data) if data else 0
            },
            tokens_used=self._tokens_used
        )

    async def _query(self, repo, criteria: Dict) -> AgentResult:
        """쿼리"""
        results = await repo.query(criteria)

        self._track_tokens(self._estimate_tokens(str(criteria)))

        return AgentResult.success_result(
            data={
                "results": [r.to_dict() for r in results],
                "count": len(results)
            },
            metrics={"result_count": len(results)},
            tokens_used=self._tokens_used
        )
```

### 4.4 QueryAgent, ValidationAgent, ExportAgent (요약)

```python
# 각 에이전트는 동일한 패턴으로 구현됩니다

class QueryAgent(BaseAgent):
    """검색/필터링 전담 에이전트"""

    def __init__(self):
        super().__init__("BLOCK_QUERY")
        # SearchBuilder, FilterBuilder, AggregateBuilder 초기화

    def get_capabilities(self) -> List[str]:
        return ["search", "filter", "aggregate", "faceted_search"]

    # execute() 구현...


class ValidationAgent(BaseAgent):
    """데이터 검증 전담 에이전트"""

    def __init__(self):
        super().__init__("BLOCK_VALIDATION")
        # SchemaValidator, BusinessValidator 초기화

    def get_capabilities(self) -> List[str]:
        return ["validate_schema", "validate_business_rules", "validate_integrity"]

    # execute() 구현...


class ExportAgent(BaseAgent):
    """데이터 내보내기 전담 에이전트"""

    def __init__(self):
        super().__init__("BLOCK_EXPORT")
        # CSVFormatter, JSONFormatter 초기화

    def get_capabilities(self) -> List[str]:
        return ["export_csv", "export_json", "export_to_sheets"]

    # execute() 구현...
```

---

## 5. 에이전트 간 통신

### 5.1 Event Bus

```python
# /src/agents/core/event_bus.py

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import asyncio
import logging
from uuid import uuid4


@dataclass
class Event:
    """이벤트"""
    type: str
    source_block: str
    data: Any = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None


class EventBus:
    """
    블럭 간 비동기 이벤트 통신

    사용법:
        bus = EventBus()

        # 구독
        bus.subscribe("file.parsed", handle_parsed_file)

        # 발행
        await bus.publish(Event(
            type="file.parsed",
            source_block="BLOCK_PARSER",
            data={"filename": "test.mp4"}
        ))
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._all_subscribers: List[Callable] = []  # 모든 이벤트 수신
        self.logger = logging.getLogger("event_bus")

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Event], Any]
    ) -> None:
        """이벤트 타입별 구독"""
        self._subscribers[event_type].append(handler)
        self.logger.debug(f"Subscribed to {event_type}")

    def subscribe_all(self, handler: Callable[[Event], Any]) -> None:
        """모든 이벤트 구독"""
        self._all_subscribers.append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """구독 해제"""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        """이벤트 발행"""
        self.logger.info(f"Publishing: {event.type} from {event.source_block}")

        # 타입별 핸들러 실행
        handlers = self._subscribers.get(event.type, [])
        for handler in handlers:
            asyncio.create_task(self._safe_call(handler, event))

        # 전체 구독자에게도 전달
        for handler in self._all_subscribers:
            asyncio.create_task(self._safe_call(handler, event))

    async def _safe_call(self, handler: Callable, event: Event) -> None:
        """예외 안전 핸들러 호출"""
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            self.logger.error(f"Event handler error: {e}", exc_info=True)

    async def request(
        self,
        target_block: str,
        action: str,
        data: Any,
        timeout: int = 30
    ) -> Any:
        """
        요청-응답 패턴

        이벤트를 발행하고 응답을 기다립니다.
        """
        correlation_id = str(uuid4())
        response_event = f"response.{correlation_id}"

        # 응답 대기 Future 설정
        future: asyncio.Future = asyncio.Future()

        def response_handler(event: Event):
            if not future.done():
                future.set_result(event.data)

        self.subscribe(response_event, response_handler)

        # 요청 발행
        await self.publish(Event(
            type=f"request.{target_block}.{action}",
            source_block="EVENT_BUS",
            data=data,
            correlation_id=correlation_id
        ))

        # 응답 대기
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request to {target_block} timed out")
        finally:
            self.unsubscribe(response_event, response_handler)
```

### 5.2 Circuit Breaker

```python
# /src/agents/core/circuit_breaker.py

from enum import Enum
from datetime import datetime, timedelta
import logging


class CircuitState(Enum):
    CLOSED = "closed"      # 정상
    OPEN = "open"          # 차단
    HALF_OPEN = "half_open"  # 복구 시도 중


class CircuitBreaker:
    """
    블럭 장애 격리

    한 블럭의 반복적인 실패가 전체 시스템에
    영향을 주지 않도록 차단합니다.

    상태:
    - CLOSED: 정상 작동, 실패 카운트
    - OPEN: 요청 차단, timeout 후 HALF_OPEN
    - HALF_OPEN: 시험적 요청 허용, 성공 시 CLOSED
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None

        self.logger = logging.getLogger("circuit_breaker")

    @property
    def state(self) -> str:
        return self._state.value

    def can_execute(self) -> bool:
        """실행 가능 여부"""
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # 복구 시간 경과 체크
            if self._last_failure_time:
                elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if elapsed > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    self.logger.info("Circuit breaker: OPEN -> HALF_OPEN")
                    return True
            return False

        # HALF_OPEN: 허용
        return True

    def record_success(self) -> None:
        """성공 기록"""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self.logger.info("Circuit breaker: HALF_OPEN -> CLOSED")
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """실패 기록"""
        self._failure_count += 1
        self._last_failure_time = datetime.utcnow()

        if self._state == CircuitState.HALF_OPEN:
            # HALF_OPEN에서 실패하면 다시 OPEN
            self._state = CircuitState.OPEN
            self.logger.warning("Circuit breaker: HALF_OPEN -> OPEN (failure during recovery)")

        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self.logger.warning(
                    f"Circuit breaker: CLOSED -> OPEN "
                    f"(failures: {self._failure_count})"
                )

    def reset(self) -> None:
        """상태 리셋"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
```

---

## 6. 워크플로우 예시

### 6.1 NAS 동기화 워크플로우

```yaml
# /src/agents/workflows/nas_sync.yaml

workflow_id: WF_NAS_SYNC
name: NAS 파일 동기화 워크플로우
version: "1.0"

context_isolation:
  enabled: true
  max_tokens_per_step: 50000

steps:
  - id: scan_files
    block_id: BLOCK_SYNC
    action: scan_nas
    inputs:
      path: "/ARCHIVE"
      sync_mode: incremental
    outputs:
      - files
      - checkpoint
    on_failure: abort
    token_budget: 40000
    timeout: 120

  - id: parse_files
    block_id: BLOCK_PARSER
    action: batch_parse
    inputs:
      files: ${scan_files.files}
    outputs:
      - parsed
    on_failure: skip
    parallel: true
    token_budget: 35000

  - id: validate_data
    block_id: BLOCK_VALIDATION
    action: validate_batch
    inputs:
      data: ${parse_files.parsed}
      schema: video_file
    outputs:
      - valid_records
      - invalid_records
    on_failure: continue
    token_budget: 30000

  - id: store_data
    block_id: BLOCK_STORAGE
    action: bulk_upsert
    inputs:
      entity_type: video_file
      data: ${validate_data.valid_records}
      options:
        upsert: true
        batch_size: 50
    outputs:
      - stored_ids
      - failed
    on_failure: rollback
    token_budget: 45000

hooks:
  on_start:
    - log: "NAS 동기화 시작"
  on_complete:
    - log: "동기화 완료: ${store_data.stored_ids} 건 저장"
    - notify:
        channel: slack
        message: "NAS 동기화 완료"
  on_error:
    - alert:
        level: error
        message: "NAS 동기화 실패"
```

---

## 7. 참조

| 문서 | 설명 |
|------|------|
| [PRD_BLOCK_AGENT_SYSTEM.md](../PRD_BLOCK_AGENT_SYSTEM.md) | PRD |
| [BLOCK_AGENT_SYSTEM.md](../architecture/BLOCK_AGENT_SYSTEM.md) | 아키텍처 설계 |
| [01_DATABASE_SCHEMA.md](./01_DATABASE_SCHEMA.md) | DB 스키마 (StorageAgent 참조) |
| [02_SYNC_SYSTEM.md](./02_SYNC_SYSTEM.md) | 동기화 시스템 (SyncAgent 참조) |
| [03_FILE_PARSER.md](./03_FILE_PARSER.md) | 파일 파서 (ParserAgent 참조) |

---

**문서 버전**: 1.0.0
**작성일**: 2025-12-09
**상태**: Draft
