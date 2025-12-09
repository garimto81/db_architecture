"""
Core 모듈 테스트

- AgentContext, AgentResult 테스트
- BaseAgent 테스트
- AgentRegistry 테스트
- EventBus 테스트
- CircuitBreaker 테스트
"""

import pytest
import asyncio
from datetime import datetime
from typing import Any, Dict, List

# Core imports
from src.agents.core.agent_context import AgentContext
from src.agents.core.agent_result import AgentResult
from src.agents.core.base_agent import BaseAgent, AgentState
from src.agents.core.agent_registry import AgentRegistry, get_registry
from src.agents.core.event_bus import EventBus, Event, get_event_bus
from src.agents.core.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerRegistry
from src.agents.core.exceptions import (
    ScopeViolationError,
    TokenLimitExceededError,
    CircuitBreakerOpenError,
)


# ─────────────────────────────────────────────────────────────────
# AgentContext Tests
# ─────────────────────────────────────────────────────────────────


class TestAgentContext:
    """AgentContext 테스트"""

    def test_create_context(self):
        """컨텍스트 생성 테스트"""
        ctx = AgentContext(
            task_id="test-task-001",
            correlation_id="corr-001",
        )

        assert ctx.task_id == "test-task-001"
        assert ctx.correlation_id == "corr-001"
        assert ctx.timeout_seconds == 300  # 기본값

    def test_context_with_input(self):
        """이전 단계 입력이 있는 컨텍스트 테스트"""
        ctx = AgentContext(
            task_id="test-task-002",
            input_from_previous={"files": ["a.mp4", "b.mp4"]},
        )

        assert ctx.input_from_previous["files"] == ["a.mp4", "b.mp4"]


# ─────────────────────────────────────────────────────────────────
# AgentResult Tests
# ─────────────────────────────────────────────────────────────────


class TestAgentResult:
    """AgentResult 테스트"""

    def test_success_result(self):
        """성공 결과 테스트"""
        result = AgentResult.success_result(
            data={"count": 10},
            metrics={"duration": 1.5},
        )

        assert result.success is True
        assert result.data["count"] == 10
        assert result.metrics["duration"] == 1.5
        assert not result.errors

    def test_failure_result(self):
        """실패 결과 테스트"""
        result = AgentResult.failure_result(
            errors=["File not found"],
            error_type="FileError",
        )

        assert result.success is False
        assert "File not found" in result.errors
        assert result.error_type == "FileError"

    def test_result_to_dict(self):
        """딕셔너리 변환 테스트"""
        result = AgentResult.success_result(data={"test": True})
        d = result.to_dict()

        assert "success" in d
        assert "data" in d
        assert d["success"] is True


# ─────────────────────────────────────────────────────────────────
# BaseAgent Tests
# ─────────────────────────────────────────────────────────────────


class DummyAgent(BaseAgent):
    """테스트용 더미 에이전트"""

    def __init__(self, block_id: str = "BLOCK_DUMMY", config: Dict = None):
        super().__init__(block_id, config)
        self._allowed_paths = ["blocks/dummy/**", "test/**"]
        self._forbidden_paths = ["**/.env", "**/secrets/**"]

    async def execute(self, context: AgentContext, input_data: Any) -> AgentResult:
        """더미 실행"""
        return AgentResult.success_result(data={"echo": input_data})

    def get_capabilities(self) -> List[str]:
        return ["test", "echo"]


class TestBaseAgent:
    """BaseAgent 테스트"""

    def test_agent_creation(self):
        """에이전트 생성 테스트"""
        agent = DummyAgent()

        assert agent.block_id == "BLOCK_DUMMY"
        assert agent.state == AgentState.IDLE
        assert "test" in agent.get_capabilities()

    def test_scope_check_allowed(self):
        """허용된 경로 접근 테스트"""
        agent = DummyAgent()

        # 허용된 경로
        assert agent._check_scope("blocks/dummy/test.py") is True
        assert agent._check_scope("test/file.txt") is True

    def test_scope_check_forbidden(self):
        """금지된 경로 접근 테스트"""
        agent = DummyAgent()

        # 금지된 경로
        with pytest.raises(ScopeViolationError):
            agent._check_scope("config/.env")

        with pytest.raises(ScopeViolationError):
            agent._check_scope("data/secrets/key.pem")

    def test_scope_check_not_allowed(self):
        """허용 목록에 없는 경로 테스트"""
        agent = DummyAgent()

        with pytest.raises(ScopeViolationError):
            agent._check_scope("other/random/file.py")

    def test_token_tracking(self):
        """토큰 추적 테스트"""
        agent = DummyAgent()
        agent._token_limit = 1000

        agent._track_tokens(500)
        assert agent.tokens_used == 500
        assert agent.tokens_remaining == 500

        agent._track_tokens(300)
        assert agent.tokens_used == 800

    def test_token_limit_exceeded(self):
        """토큰 한도 초과 테스트"""
        agent = DummyAgent()
        agent._token_limit = 100

        with pytest.raises(TokenLimitExceededError):
            agent._track_tokens(150)

    def test_estimate_tokens(self):
        """토큰 추정 테스트"""
        agent = DummyAgent()

        # ASCII 문자
        tokens = agent._estimate_tokens("hello world")
        assert tokens > 0

        # 한글 포함
        tokens_kr = agent._estimate_tokens("안녕하세요")
        assert tokens_kr > 0

    def test_memory_operations(self):
        """메모리 작업 테스트"""
        agent = DummyAgent()

        agent.remember("key1", "value1")
        assert agent.recall("key1") == "value1"
        assert agent.recall("nonexistent", "default") == "default"

        agent.forget("key1")
        assert agent.recall("key1") is None

    def test_tool_registration(self):
        """도구 등록 테스트"""
        agent = DummyAgent()

        def dummy_tool():
            pass

        agent.register_tool("my_tool", dummy_tool)
        assert agent.has_tool("my_tool")
        assert agent.get_tool("my_tool") == dummy_tool

    @pytest.mark.asyncio
    async def test_execute(self):
        """실행 테스트"""
        agent = DummyAgent()
        ctx = AgentContext(task_id="test-001")

        result = await agent.execute(ctx, {"message": "hello"})

        assert result.success is True
        assert result.data["echo"]["message"] == "hello"


# ─────────────────────────────────────────────────────────────────
# AgentRegistry Tests
# ─────────────────────────────────────────────────────────────────


class TestAgentRegistry:
    """AgentRegistry 테스트"""

    def test_register_agent(self):
        """에이전트 등록 테스트"""
        registry = AgentRegistry()
        agent = DummyAgent()

        registry.register(agent)

        assert "BLOCK_DUMMY" in registry
        assert registry.get_agent("BLOCK_DUMMY") == agent

    def test_unregister_agent(self):
        """에이전트 해제 테스트"""
        registry = AgentRegistry()
        agent = DummyAgent()

        registry.register(agent)
        registry.unregister("BLOCK_DUMMY")

        assert "BLOCK_DUMMY" not in registry

    def test_find_by_capability(self):
        """능력 기반 검색 테스트"""
        registry = AgentRegistry()
        agent = DummyAgent()

        registry.register(agent)

        found = registry.find_by_capability("test")
        assert len(found) == 1
        assert found[0] == agent

        not_found = registry.find_by_capability("nonexistent")
        assert len(not_found) == 0


# ─────────────────────────────────────────────────────────────────
# EventBus Tests
# ─────────────────────────────────────────────────────────────────


class TestEventBus:
    """EventBus 테스트"""

    @pytest.mark.asyncio
    async def test_publish_subscribe(self):
        """발행/구독 테스트"""
        bus = EventBus()
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        bus.subscribe("test.event", handler)

        event = Event(type="test.event", source_block="TEST", data={"msg": "hello"})
        await bus.publish(event)

        # 비동기 핸들러 실행 대기
        await asyncio.sleep(0.1)

        assert len(received_events) == 1
        assert received_events[0].data["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_subscribe_all(self):
        """전체 이벤트 구독 테스트"""
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe_all(handler)

        await bus.publish(Event(type="event.a", source_block="A"))
        await bus.publish(Event(type="event.b", source_block="B"))

        await asyncio.sleep(0.1)

        assert len(received) == 2

    def test_event_history(self):
        """이벤트 히스토리 테스트"""
        bus = EventBus()

        # 동기적으로 히스토리 확인을 위해 직접 추가
        event = Event(type="test", source_block="TEST")
        bus._event_history.append(event)

        history = bus.get_history(limit=10)
        assert len(history) >= 1


# ─────────────────────────────────────────────────────────────────
# CircuitBreaker Tests
# ─────────────────────────────────────────────────────────────────


class TestCircuitBreaker:
    """CircuitBreaker 테스트"""

    def test_initial_state(self):
        """초기 상태 테스트"""
        cb = CircuitBreaker(name="test")

        assert cb.circuit_state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_transition_to_open(self):
        """OPEN 상태 전이 테스트"""
        cb = CircuitBreaker(failure_threshold=3, name="test")

        # 3번 실패
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()

        assert cb.circuit_state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_success_resets_count(self):
        """성공 시 실패 카운트 리셋 테스트"""
        cb = CircuitBreaker(failure_threshold=5, name="test")

        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        cb.record_success()
        assert cb.failure_count == 0

    def test_manual_reset(self):
        """수동 리셋 테스트"""
        cb = CircuitBreaker(failure_threshold=1, name="test")

        cb.record_failure()
        assert cb.circuit_state == CircuitState.OPEN

        cb.reset()
        assert cb.circuit_state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_force_open(self):
        """강제 OPEN 테스트"""
        cb = CircuitBreaker(name="test")

        cb.force_open()
        assert cb.circuit_state == CircuitState.OPEN

    def test_stats(self):
        """통계 정보 테스트"""
        cb = CircuitBreaker(failure_threshold=5, name="test_stats")

        stats = cb.get_stats()
        assert stats["name"] == "test_stats"
        assert stats["state"] == "closed"
        assert stats["failure_threshold"] == 5


class TestCircuitBreakerRegistry:
    """CircuitBreakerRegistry 테스트"""

    def test_get_or_create(self):
        """조회 또는 생성 테스트"""
        registry = CircuitBreakerRegistry()

        cb1 = registry.get_or_create("block_a")
        cb2 = registry.get_or_create("block_a")

        assert cb1 is cb2  # 동일 인스턴스

    def test_reset_all(self):
        """전체 리셋 테스트"""
        registry = CircuitBreakerRegistry()

        cb1 = registry.get_or_create("block_a", failure_threshold=1)
        cb2 = registry.get_or_create("block_b", failure_threshold=1)

        cb1.record_failure()
        cb2.record_failure()

        assert cb1.circuit_state == CircuitState.OPEN
        assert cb2.circuit_state == CircuitState.OPEN

        registry.reset_all()

        assert cb1.circuit_state == CircuitState.CLOSED
        assert cb2.circuit_state == CircuitState.CLOSED


# ─────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────


class TestCoreIntegration:
    """Core 모듈 통합 테스트"""

    @pytest.mark.asyncio
    async def test_agent_with_circuit_breaker(self):
        """에이전트와 Circuit Breaker 통합 테스트"""
        agent = DummyAgent()
        cb = CircuitBreaker(failure_threshold=2, name=agent.block_id)

        # 정상 실행
        if cb.can_execute():
            ctx = AgentContext(task_id="test-001")
            result = await agent.execute(ctx, {"test": True})
            cb.record_success()

        assert result.success is True
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_agent_with_event_bus(self):
        """에이전트와 EventBus 통합 테스트"""
        agent = DummyAgent()
        bus = EventBus()
        results = []

        async def on_complete(event: Event):
            results.append(event.data)

        bus.subscribe("agent.complete", on_complete)

        # 에이전트 실행 후 이벤트 발행
        ctx = AgentContext(task_id="test-001")
        result = await agent.execute(ctx, {"msg": "hello"})

        await bus.publish(
            Event(
                type="agent.complete",
                source_block=agent.block_id,
                data=result.to_dict(),
            )
        )

        await asyncio.sleep(0.1)

        assert len(results) == 1
        assert results[0]["success"] is True
