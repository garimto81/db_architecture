"""
Core Infrastructure for Block Agent System

이 모듈은 에이전트 시스템의 핵심 인프라를 제공합니다.

Classes:
    BaseAgent: 모든 에이전트의 추상 기본 클래스
    AgentContext: 에이전트 실행 컨텍스트
    AgentResult: 에이전트 실행 결과
    AgentRegistry: 에이전트 중앙 등록소
    EventBus: 블럭 간 비동기 통신
    CircuitBreaker: 장애 격리
"""

from .exceptions import (
    AgentError,
    ScopeViolationError,
    TokenLimitExceededError,
    AgentExecutionError,
    BlockRulesValidationError,
    CircuitBreakerOpenError,
)
from .agent_context import AgentContext, WorkflowContext
from .agent_result import AgentResult
from .base_agent import BaseAgent, AgentState
from .agent_registry import AgentRegistry, get_registry
from .event_bus import EventBus, Event
from .circuit_breaker import CircuitBreaker, CircuitState

__all__ = [
    # Exceptions
    "AgentError",
    "ScopeViolationError",
    "TokenLimitExceededError",
    "AgentExecutionError",
    "BlockRulesValidationError",
    "CircuitBreakerOpenError",
    # Context & Result
    "AgentContext",
    "WorkflowContext",
    "AgentResult",
    # Base
    "BaseAgent",
    "AgentState",
    # Registry
    "AgentRegistry",
    "get_registry",
    # Communication
    "EventBus",
    "Event",
    # Fault Tolerance
    "CircuitBreaker",
    "CircuitState",
]
