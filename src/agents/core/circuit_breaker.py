"""
Circuit Breaker - 블럭 장애 격리

한 블럭의 반복적인 실패가 전체 시스템에 영향을 주지 않도록 차단합니다.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Callable, TypeVar, Any
from functools import wraps
import asyncio
import logging

from .exceptions import CircuitBreakerOpenError


class CircuitState(Enum):
    """Circuit Breaker 상태"""

    CLOSED = "closed"  # 정상 - 요청 허용
    OPEN = "open"  # 차단 - 요청 거부
    HALF_OPEN = "half_open"  # 복구 시도 - 제한적 허용


T = TypeVar("T")


class CircuitBreaker:
    """
    블럭 장애 격리 (Circuit Breaker Pattern)

    한 블럭의 반복적인 실패가 전체 시스템에
    영향을 주지 않도록 차단합니다.

    상태 전이:
    - CLOSED: 정상 작동, 실패 카운트
    - OPEN: 요청 차단, recovery_timeout 후 HALF_OPEN으로 전이
    - HALF_OPEN: 시험적 요청 허용, 성공 시 CLOSED로 복귀

    사용법:
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

        # 실행 전 체크
        if cb.can_execute():
            try:
                result = await some_operation()
                cb.record_success()
            except Exception:
                cb.record_failure()
        else:
            raise CircuitBreakerOpenError("BLOCK_XYZ")

        # 또는 데코레이터 사용
        @cb.wrap
        async def some_operation():
            ...

    Attributes:
        failure_threshold: OPEN으로 전환되는 실패 횟수
        recovery_timeout: OPEN에서 HALF_OPEN으로 전환되는 시간 (초)
        success_threshold: HALF_OPEN에서 CLOSED로 전환되는 성공 횟수
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
        name: Optional[str] = None,
    ):
        """
        Args:
            failure_threshold: OPEN 전환 실패 횟수 (기본: 5)
            recovery_timeout: 복구 대기 시간 초 (기본: 60)
            success_threshold: CLOSED 복귀 성공 횟수 (기본: 2)
            name: Circuit Breaker 이름 (로깅용)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.name = name or "unnamed"

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_state_change: datetime = datetime.utcnow()

        self.logger = logging.getLogger(f"circuit_breaker.{self.name}")

    @property
    def state(self) -> str:
        """현재 상태 문자열"""
        return self._state.value

    @property
    def circuit_state(self) -> CircuitState:
        """현재 상태 Enum"""
        return self._state

    @property
    def failure_count(self) -> int:
        """현재 실패 횟수"""
        return self._failure_count

    def can_execute(self) -> bool:
        """
        실행 가능 여부

        Returns:
            True if 요청 허용, False if 차단
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # 복구 시간 경과 체크
            if self._last_failure_time:
                elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if elapsed > self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
            return False

        # HALF_OPEN: 허용
        return True

    def record_success(self) -> None:
        """
        성공 기록

        HALF_OPEN 상태에서 success_threshold만큼 성공하면 CLOSED로 전환
        """
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            self.logger.debug(
                f"Success in HALF_OPEN: {self._success_count}/{self.success_threshold}"
            )
            if self._success_count >= self.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        else:
            # CLOSED 상태에서 성공하면 실패 카운트 리셋
            self._failure_count = 0

    def record_failure(self) -> None:
        """
        실패 기록

        failure_threshold 도달 시 OPEN으로 전환
        HALF_OPEN에서 실패하면 다시 OPEN으로
        """
        self._failure_count += 1
        self._last_failure_time = datetime.utcnow()

        if self._state == CircuitState.HALF_OPEN:
            # HALF_OPEN에서 실패하면 다시 OPEN
            self._transition_to(CircuitState.OPEN)
            self.logger.warning(
                f"Circuit breaker '{self.name}': HALF_OPEN -> OPEN (failure during recovery)"
            )

        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                self.logger.warning(
                    f"Circuit breaker '{self.name}': CLOSED -> OPEN "
                    f"(failures: {self._failure_count})"
                )

    def _transition_to(self, new_state: CircuitState) -> None:
        """상태 전이"""
        old_state = self._state
        self._state = new_state
        self._last_state_change = datetime.utcnow()

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self.logger.info(f"Circuit breaker '{self.name}': {old_state.value} -> CLOSED")

        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            self.logger.info(f"Circuit breaker '{self.name}': {old_state.value} -> HALF_OPEN")

        elif new_state == CircuitState.OPEN:
            self._success_count = 0

    def reset(self) -> None:
        """상태 리셋 (수동 복구)"""
        self._transition_to(CircuitState.CLOSED)
        self._last_failure_time = None
        self.logger.info(f"Circuit breaker '{self.name}': manually reset")

    def force_open(self) -> None:
        """강제 OPEN (수동 차단)"""
        self._transition_to(CircuitState.OPEN)
        self._last_failure_time = datetime.utcnow()
        self.logger.warning(f"Circuit breaker '{self.name}': manually opened")

    def wrap(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        함수를 Circuit Breaker로 래핑하는 데코레이터

        Example:
            cb = CircuitBreaker()

            @cb.wrap
            async def risky_operation():
                ...
        """
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                if not self.can_execute():
                    raise CircuitBreakerOpenError(self.name)
                try:
                    result = await func(*args, **kwargs)
                    self.record_success()
                    return result
                except Exception:
                    self.record_failure()
                    raise

            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> T:
                if not self.can_execute():
                    raise CircuitBreakerOpenError(self.name)
                try:
                    result = func(*args, **kwargs)
                    self.record_success()
                    return result
                except Exception:
                    self.record_failure()
                    raise

            return sync_wrapper

    def get_stats(self) -> dict:
        """통계 정보 반환"""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": (
                self._last_failure_time.isoformat()
                if self._last_failure_time
                else None
            ),
            "last_state_change": self._last_state_change.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name}, state={self.state}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )


class CircuitBreakerRegistry:
    """
    Circuit Breaker 중앙 관리

    블럭별 Circuit Breaker를 관리합니다.
    """

    def __init__(
        self,
        default_failure_threshold: int = 5,
        default_recovery_timeout: int = 60,
    ):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._default_failure_threshold = default_failure_threshold
        self._default_recovery_timeout = default_recovery_timeout

    def get_or_create(
        self,
        name: str,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[int] = None,
    ) -> CircuitBreaker:
        """
        Circuit Breaker 조회 또는 생성

        Args:
            name: Circuit Breaker 이름 (보통 block_id)
            failure_threshold: 실패 임계값 (None이면 기본값)
            recovery_timeout: 복구 타임아웃 (None이면 기본값)

        Returns:
            CircuitBreaker 인스턴스
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold or self._default_failure_threshold,
                recovery_timeout=recovery_timeout or self._default_recovery_timeout,
                name=name,
            )
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Circuit Breaker 조회"""
        return self._breakers.get(name)

    def get_all_stats(self) -> dict[str, dict]:
        """모든 Circuit Breaker 통계"""
        return {name: cb.get_stats() for name, cb in self._breakers.items()}

    def reset_all(self) -> None:
        """모든 Circuit Breaker 리셋"""
        for cb in self._breakers.values():
            cb.reset()

    def __contains__(self, name: str) -> bool:
        return name in self._breakers

    def __len__(self) -> int:
        return len(self._breakers)
