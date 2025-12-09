"""
BaseAgent 추상 클래스

모든 블럭 에이전트의 기본 클래스입니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
import logging
import yaml

from .agent_context import AgentContext
from .agent_result import AgentResult
from .exceptions import (
    ScopeViolationError,
    TokenLimitExceededError,
    AgentExecutionError,
    BlockRulesValidationError,
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

            def get_capabilities(self) -> List[str]:
                return ["parse_filename", "detect_project"]

    Attributes:
        block_id: 블럭 고유 식별자
        config: 에이전트 설정
        state: 현재 상태
        logger: 로거 인스턴스
    """

    # 기본 블럭 규칙 디렉토리
    BLOCKS_DIR = Path("blocks")

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

        # 블럭 규칙 (기본값)
        self._block_rules: Dict[str, Any] = {}
        self._allowed_paths: List[str] = []
        self._forbidden_paths: List[str] = []
        self._token_limit: int = 50000
        self._file_limit: int = 30

        # 블럭 규칙 로드 시도
        self._load_block_rules()

    # ─────────────────────────────────────────────────────────────────
    # Block Rules Management
    # ─────────────────────────────────────────────────────────────────

    def _load_block_rules(self) -> None:
        """블럭 규칙 파일 로드 및 파싱"""
        block_name = self.block_id.lower().replace("block_", "")
        rules_path = self.BLOCKS_DIR / block_name / ".block_rules"

        try:
            if rules_path.exists():
                with open(rules_path, "r", encoding="utf-8") as f:
                    self._block_rules = yaml.safe_load(f) or {}

                # 범위 설정 추출
                scope = self._block_rules.get("scope", {})
                self._allowed_paths = scope.get(
                    "allowed_paths", [f"blocks/{block_name}/**"]
                )
                self._forbidden_paths = scope.get("forbidden_paths", [])

                # 제한 설정 추출
                limits = self._block_rules.get("limits", {})
                self._token_limit = limits.get("max_tokens", 50000)
                self._file_limit = limits.get("max_files", 30)

                self.logger.info(f"Loaded block rules: {rules_path}")
            else:
                self._use_default_rules()

        except yaml.YAMLError as e:
            raise BlockRulesValidationError(f"Invalid YAML: {e}", self.block_id)

    def _use_default_rules(self) -> None:
        """기본 규칙 적용 (규칙 파일 없을 때)"""
        block_name = self.block_id.lower().replace("block_", "")
        self._allowed_paths = [f"blocks/{block_name}/**", f"src/agents/blocks/{block_name}/**"]
        self._forbidden_paths = ["config/credentials/**", "**/.env", "**/*.key"]
        self._token_limit = 50000
        self._file_limit = 30
        self.logger.debug(f"Using default rules for {self.block_id}")

    @property
    def block_rules(self) -> Dict[str, Any]:
        """블럭 규칙 반환"""
        return self._block_rules.copy()

    @property
    def role_description(self) -> str:
        """에이전트 역할 설명 반환"""
        return self._block_rules.get("role", f"{self.block_id} 전담 에이전트")

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

        Example:
            self._check_scope("blocks/parser/patterns/wsop.py")  # OK
            self._check_scope("blocks/sync/connector.py")  # Raises ScopeViolationError
        """
        # 정규화된 경로 (Windows 경로 호환)
        normalized_path = file_path.replace("\\", "/")

        # 1. 금지 경로 체크 (우선)
        for pattern in self._forbidden_paths:
            if fnmatch(normalized_path, pattern):
                self.logger.warning(f"Scope violation (forbidden): {file_path}")
                raise ScopeViolationError(
                    block_id=self.block_id,
                    attempted_path=file_path,
                    reason=f"Path matches forbidden pattern: {pattern}",
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
            reason=f"Path not in allowed scope. Allowed: {self._allowed_paths}",
        )

    def _check_scope_batch(self, file_paths: List[str]) -> List[str]:
        """
        여러 파일의 접근 범위 일괄 검사

        Args:
            file_paths: 검사할 파일 경로 목록

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
        self._metrics["tokens_used"] = self._tokens_used

        if self._tokens_used > self._token_limit:
            raise TokenLimitExceededError(
                block_id=self.block_id,
                used=self._tokens_used,
                limit=self._token_limit,
            )

    def _estimate_tokens(self, content: str) -> int:
        """
        문자열의 토큰 수 추정

        간단한 휴리스틱:
        - ASCII 문자: 4글자당 1토큰
        - 비ASCII(한글 등): 2글자당 1토큰

        Args:
            content: 토큰 수를 추정할 문자열

        Returns:
            추정 토큰 수
        """
        if not content:
            return 0

        ascii_chars = sum(1 for c in content if ord(c) < 128)
        non_ascii_chars = len(content) - ascii_chars

        return (ascii_chars // 4) + (non_ascii_chars // 2) + 1

    def _reset_tokens(self) -> None:
        """토큰 카운터 리셋"""
        self._tokens_used = 0
        self._metrics["tokens_used"] = 0

    @property
    def tokens_used(self) -> int:
        """사용한 토큰 수"""
        return self._tokens_used

    @property
    def tokens_remaining(self) -> int:
        """남은 토큰 수"""
        return max(0, self._token_limit - self._tokens_used)

    @property
    def token_usage_percent(self) -> float:
        """토큰 사용률 (0-100%)"""
        if self._token_limit == 0:
            return 0.0
        return (self._tokens_used / self._token_limit) * 100

    # ─────────────────────────────────────────────────────────────────
    # Lifecycle Methods
    # ─────────────────────────────────────────────────────────────────

    async def pre_execute(self, context: AgentContext) -> None:
        """
        실행 전 준비 단계

        - 상태 변경
        - 컨텍스트 검증
        - 토큰 리셋
        """
        self.state = AgentState.INITIALIZING
        self.logger.info(f"Pre-execute: task_id={context.task_id[:8]}...")

        # 컨텍스트 검증
        self._validate_context(context)

        # 토큰 리셋 (새 태스크)
        self._reset_tokens()

        self.state = AgentState.PROCESSING

    def _validate_context(self, context: AgentContext) -> None:
        """컨텍스트 유효성 검증"""
        if not context.task_id:
            raise AgentExecutionError("task_id is required", self.block_id)

        # 예상 토큰이 한도를 초과하는지 체크
        if context.estimated_tokens and context.estimated_tokens > self._token_limit:
            self.logger.warning(
                f"Estimated tokens ({context.estimated_tokens}) may exceed limit ({self._token_limit})"
            )

    async def post_execute(self, result: AgentResult) -> None:
        """
        실행 후 정리 단계

        - 메트릭 기록
        - 상태 업데이트
        """
        self.state = AgentState.COMPLETED if result.success else AgentState.ERROR

        # 메트릭 업데이트
        result.metrics.update(
            {
                "tokens_used": self._tokens_used,
                "token_usage_percent": self.token_usage_percent,
            }
        )

        self.logger.info(
            f"Post-execute: success={result.success}, tokens={self._tokens_used}"
        )

    async def handle_error(
        self, error: Exception, context: AgentContext
    ) -> AgentResult:
        """
        에러 처리

        표준화된 에러 처리 및 AgentResult 생성

        Args:
            error: 발생한 예외
            context: 실행 컨텍스트

        Returns:
            실패 상태의 AgentResult
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
            error_type=type(error).__name__,
        )

    # ─────────────────────────────────────────────────────────────────
    # Abstract Methods (구현 필수)
    # ─────────────────────────────────────────────────────────────────

    @abstractmethod
    async def execute(self, context: AgentContext, input_data: Any) -> AgentResult:
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
        """
        도구 등록

        Args:
            name: 도구 이름
            tool: 도구 인스턴스
        """
        self._tools[name] = tool
        self.logger.debug(f"Registered tool: {name}")

    def get_tool(self, name: str) -> Any:
        """
        도구 조회

        Args:
            name: 도구 이름

        Returns:
            도구 인스턴스

        Raises:
            KeyError: 등록되지 않은 도구
        """
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def has_tool(self, name: str) -> bool:
        """도구 존재 여부"""
        return name in self._tools

    @property
    def tools(self) -> Dict[str, Any]:
        """등록된 모든 도구 (복사본)"""
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

    def to_dict(self) -> Dict[str, Any]:
        """에이전트 정보를 딕셔너리로 변환"""
        return {
            "block_id": self.block_id,
            "state": self.state.value,
            "capabilities": self.get_capabilities(),
            "tokens_used": self._tokens_used,
            "token_limit": self._token_limit,
            "token_usage_percent": self.token_usage_percent,
            "metrics": self._metrics.copy(),
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} block_id={self.block_id} state={self.state.value}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.block_id})"
