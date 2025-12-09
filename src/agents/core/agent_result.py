"""
에이전트 실행 결과

모든 에이전트는 이 형식으로 결과를 반환합니다.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class AgentResult:
    """
    에이전트 실행 결과

    모든 에이전트는 execute() 메서드에서 이 형식으로 결과를 반환합니다.

    Attributes:
        success: 실행 성공 여부
        data: 실행 결과 데이터
        errors: 발생한 에러 목록
        warnings: 경고 메시지 목록
        metrics: 실행 메트릭 (소요 시간, 처리 건수 등)
        next_actions: 후속 권장 액션 목록
        tokens_used: 사용한 토큰 수
        error_type: 에러 타입 (실패 시)

    Example:
        # 성공 결과
        result = AgentResult.success_result(
            data={"parsed": parsed_data},
            metrics={"confidence": 0.95}
        )

        # 실패 결과
        result = AgentResult.failure_result(
            error="File not found",
            error_type="FileNotFoundError"
        )
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

    @property
    def first_error(self) -> Optional[str]:
        """첫 번째 에러 반환"""
        return self.errors[0] if self.errors else None

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
            "completed_at": self.completed_at.isoformat(),
        }

    @classmethod
    def success_result(
        cls,
        data: Any,
        metrics: Optional[Dict[str, float]] = None,
        tokens_used: int = 0,
        next_actions: Optional[List[str]] = None,
    ) -> "AgentResult":
        """
        성공 결과 생성 헬퍼

        Args:
            data: 결과 데이터
            metrics: 실행 메트릭
            tokens_used: 사용한 토큰 수
            next_actions: 후속 권장 액션

        Returns:
            성공 상태의 AgentResult
        """
        return cls(
            success=True,
            data=data,
            metrics=metrics or {},
            tokens_used=tokens_used,
            next_actions=next_actions or [],
        )

    @classmethod
    def failure_result(
        cls,
        error: str,
        error_type: str = "AgentError",
        tokens_used: int = 0,
        next_actions: Optional[List[str]] = None,
    ) -> "AgentResult":
        """
        실패 결과 생성 헬퍼

        Args:
            error: 에러 메시지
            error_type: 에러 타입
            tokens_used: 사용한 토큰 수
            next_actions: 후속 권장 액션

        Returns:
            실패 상태의 AgentResult
        """
        return cls(
            success=False,
            errors=[error],
            error_type=error_type,
            tokens_used=tokens_used,
            next_actions=next_actions or ["retry", "manual_review"],
        )

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else f"FAILED({self.error_type})"
        return f"AgentResult({status}, tokens={self.tokens_used})"

    def __bool__(self) -> bool:
        """불리언 변환 - success 값 반환"""
        return self.success
