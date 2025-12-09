"""
에이전트 실행 컨텍스트

각 에이전트 실행 시 전달되는 컨텍스트 정보를 정의합니다.
"""

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

    Example:
        context = AgentContext(
            timeout_seconds=60,
            estimated_tokens=30000
        )
    """

    # 필수 필드 (자동 생성)
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
            "estimated_tokens": self.estimated_tokens,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"AgentContext(task_id={self.task_id[:8]}..., "
            f"workflow_id={self.workflow_id}, step_id={self.step_id})"
        )


@dataclass
class WorkflowContext:
    """
    워크플로우 전체 컨텍스트

    여러 에이전트에 걸친 워크플로우 실행 시 사용됩니다.

    Attributes:
        workflow_id: 워크플로우 고유 ID
        workflow_name: 워크플로우 이름
        current_step: 현재 실행 중인 단계 번호
        total_steps: 전체 단계 수
        status: 워크플로우 상태
        step_results: 각 단계별 결과
        accumulated_data: 누적 데이터 (단계 간 전달)
        errors: 발생한 에러 목록
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

    def cancel(self) -> None:
        """워크플로우 취소"""
        self.status = "cancelled"
        self.completed_at = datetime.utcnow()

    def save_step_result(self, step_id: str, result: Any) -> None:
        """단계 결과 저장"""
        self.step_results[step_id] = result

    def get_step_result(self, step_id: str) -> Any:
        """단계 결과 조회"""
        return self.step_results.get(step_id)

    def add_error(self, error: str) -> None:
        """에러 추가"""
        self.errors.append(error)

    @property
    def duration_seconds(self) -> Optional[float]:
        """실행 시간 (초)"""
        if not self.started_at:
            return None
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    @property
    def is_running(self) -> bool:
        """실행 중 여부"""
        return self.status == "running"

    @property
    def is_completed(self) -> bool:
        """완료 여부 (성공 또는 실패)"""
        return self.status in ("completed", "failed", "cancelled")

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"WorkflowContext(id={self.workflow_id[:8]}..., "
            f"name={self.workflow_name}, status={self.status}, "
            f"step={self.current_step}/{self.total_steps})"
        )
