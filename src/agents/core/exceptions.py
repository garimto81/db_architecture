"""
에이전트 시스템 커스텀 예외

모든 에이전트 관련 예외는 AgentError를 상속받습니다.
"""

from typing import Optional


class AgentError(Exception):
    """에이전트 시스템 기본 예외"""

    def __init__(self, message: str, block_id: Optional[str] = None):
        self.message = message
        self.block_id = block_id
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.block_id:
            return f"[{self.block_id}] {self.message}"
        return self.message


class ScopeViolationError(AgentError):
    """
    범위 위반 예외

    에이전트가 허용되지 않은 경로에 접근하려 할 때 발생합니다.

    Attributes:
        attempted_path: 접근 시도한 경로
        reason: 거부 사유
    """

    def __init__(
        self,
        block_id: str,
        attempted_path: str,
        reason: str = "Path not in allowed scope"
    ):
        self.attempted_path = attempted_path
        self.reason = reason
        message = f"Scope violation: {attempted_path} - {reason}"
        super().__init__(message, block_id)


class TokenLimitExceededError(AgentError):
    """
    토큰 한도 초과 예외

    에이전트가 할당된 토큰 한도를 초과했을 때 발생합니다.

    Attributes:
        used: 사용한 토큰 수
        limit: 토큰 한도
    """

    def __init__(self, block_id: str, used: int, limit: int):
        self.used = used
        self.limit = limit
        message = f"Token limit exceeded: {used}/{limit}"
        super().__init__(message, block_id)


class AgentExecutionError(AgentError):
    """
    에이전트 실행 오류

    에이전트 실행 중 발생하는 일반적인 오류입니다.

    Attributes:
        original_error: 원본 예외 (있는 경우)
    """

    def __init__(
        self,
        message: str,
        block_id: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        self.original_error = original_error
        super().__init__(message, block_id)


class BlockRulesValidationError(AgentError):
    """
    블럭 규칙 검증 오류

    .block_rules 파일 파싱 또는 검증 실패 시 발생합니다.
    """

    def __init__(self, message: str, block_id: Optional[str] = None):
        super().__init__(f"Block rules validation failed: {message}", block_id)


class CircuitBreakerOpenError(AgentError):
    """
    Circuit Breaker Open 상태 예외

    대상 블럭의 Circuit Breaker가 Open 상태일 때 발생합니다.
    """

    def __init__(self, block_id: str):
        super().__init__(
            f"Circuit breaker is open - requests are blocked",
            block_id
        )


class WorkflowError(AgentError):
    """워크플로우 관련 오류"""

    def __init__(
        self,
        message: str,
        workflow_id: Optional[str] = None,
        step_id: Optional[str] = None
    ):
        self.workflow_id = workflow_id
        self.step_id = step_id
        prefix = ""
        if workflow_id:
            prefix += f"[WF:{workflow_id}]"
        if step_id:
            prefix += f"[Step:{step_id}]"
        full_message = f"{prefix} {message}" if prefix else message
        super().__init__(full_message)


class WorkflowNotFoundError(WorkflowError):
    """워크플로우를 찾을 수 없음"""

    def __init__(self, workflow_name: str):
        super().__init__(f"Workflow not found: {workflow_name}")


class AgentNotFoundError(AgentError):
    """에이전트를 찾을 수 없음"""

    def __init__(self, block_id: str):
        super().__init__(f"Agent not registered: {block_id}", block_id)


class CapabilityNotFoundError(AgentError):
    """능력을 찾을 수 없음"""

    def __init__(self, block_id: str, capability: str):
        self.capability = capability
        super().__init__(
            f"Capability '{capability}' not found",
            block_id
        )
