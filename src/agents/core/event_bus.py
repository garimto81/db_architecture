"""
EventBus - 블럭 간 비동기 이벤트 통신

Pub/Sub 패턴을 사용하여 블럭 간 느슨한 결합 통신을 지원합니다.
"""

from typing import Any, Callable, Dict, List, Optional, Awaitable, Union
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from uuid import uuid4
import asyncio
import logging


@dataclass
class Event:
    """
    이벤트 데이터 클래스

    Attributes:
        type: 이벤트 타입 (예: "file.parsed", "sync.completed")
        source_block: 이벤트 발생 블럭 ID
        data: 이벤트 페이로드
        event_id: 이벤트 고유 ID
        timestamp: 이벤트 발생 시간
        correlation_id: 연관 워크플로우 ID (추적용)
    """

    type: str
    source_block: str
    data: Any = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "type": self.type,
            "source_block": self.source_block,
            "data": self.data,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
        }

    def __repr__(self) -> str:
        return f"Event(type={self.type}, source={self.source_block}, id={self.event_id[:8]}...)"


# 핸들러 타입 정의
EventHandler = Callable[[Event], Union[None, Awaitable[None]]]


class EventBus:
    """
    블럭 간 비동기 이벤트 통신

    Pub/Sub 패턴을 사용하여 블럭 간 느슨한 결합 통신을 지원합니다.

    사용법:
        bus = EventBus()

        # 구독
        async def handle_parsed_file(event: Event):
            print(f"File parsed: {event.data}")

        bus.subscribe("file.parsed", handle_parsed_file)

        # 발행
        await bus.publish(Event(
            type="file.parsed",
            source_block="BLOCK_PARSER",
            data={"filename": "test.mp4", "success": True}
        ))

        # 요청-응답 패턴
        result = await bus.request(
            target_block="BLOCK_STORAGE",
            action="save",
            data={"entity": "video_file", "record": {...}}
        )
    """

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._all_subscribers: List[EventHandler] = []  # 모든 이벤트 수신
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self.logger = logging.getLogger("event_bus")
        self._event_history: List[Event] = []
        self._max_history: int = 1000

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        이벤트 타입별 구독

        Args:
            event_type: 구독할 이벤트 타입 (예: "file.parsed")
            handler: 이벤트 핸들러 함수 (async/sync 모두 가능)
        """
        self._subscribers[event_type].append(handler)
        self.logger.debug(f"Subscribed to '{event_type}'")

    def subscribe_pattern(self, pattern: str, handler: EventHandler) -> None:
        """
        패턴 기반 구독 (예: "file.*")

        Note: 현재는 단순 prefix 매칭만 지원
        """
        # 와일드카드 처리
        if pattern.endswith("*"):
            base = pattern[:-1]
            # 모든 이벤트를 받아서 필터링하는 래퍼 생성
            async def pattern_handler(event: Event):
                if event.type.startswith(base):
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        await result

            self._all_subscribers.append(pattern_handler)
        else:
            self.subscribe(pattern, handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """
        모든 이벤트 구독

        Args:
            handler: 모든 이벤트를 수신할 핸들러
        """
        self._all_subscribers.append(handler)
        self.logger.debug("Subscribed to all events")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """
        구독 해제

        Args:
            event_type: 이벤트 타입
            handler: 해제할 핸들러

        Returns:
            True if 해제됨, False if 핸들러가 없음
        """
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            return True
        return False

    async def publish(self, event: Event) -> None:
        """
        이벤트 발행

        등록된 모든 핸들러에게 이벤트를 비동기적으로 전달합니다.

        Args:
            event: 발행할 이벤트
        """
        self.logger.debug(f"Publishing: {event.type} from {event.source_block}")

        # 히스토리 저장
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # 타입별 핸들러 실행
        handlers = self._subscribers.get(event.type, [])
        for handler in handlers:
            asyncio.create_task(self._safe_call(handler, event))

        # 전체 구독자에게도 전달
        for handler in self._all_subscribers:
            asyncio.create_task(self._safe_call(handler, event))

        # 응답 대기 중인 요청 체크
        if event.correlation_id and event.correlation_id in self._pending_responses:
            future = self._pending_responses[event.correlation_id]
            if not future.done():
                future.set_result(event.data)

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """예외 안전 핸들러 호출"""
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            self.logger.error(
                f"Event handler error for '{event.type}': {e}",
                exc_info=True
            )

    async def publish_and_wait(
        self,
        event: Event,
        timeout: float = 30.0
    ) -> Optional[Any]:
        """
        이벤트 발행 후 응답 대기

        Args:
            event: 발행할 이벤트
            timeout: 대기 시간 (초)

        Returns:
            응답 데이터 또는 None (타임아웃)
        """
        # correlation_id 설정
        if not event.correlation_id:
            event.correlation_id = str(uuid4())

        # Future 생성
        future: asyncio.Future = asyncio.Future()
        self._pending_responses[event.correlation_id] = future

        try:
            # 이벤트 발행
            await self.publish(event)

            # 응답 대기
            return await asyncio.wait_for(future, timeout=timeout)

        except asyncio.TimeoutError:
            self.logger.warning(f"Event response timeout: {event.type}")
            return None
        finally:
            # 정리
            self._pending_responses.pop(event.correlation_id, None)

    async def request(
        self,
        target_block: str,
        action: str,
        data: Any,
        timeout: float = 30.0,
        correlation_id: Optional[str] = None,
    ) -> Any:
        """
        요청-응답 패턴

        특정 블럭에 요청을 보내고 응답을 기다립니다.

        Args:
            target_block: 대상 블럭 ID
            action: 요청 액션
            data: 요청 데이터
            timeout: 대기 시간 (초)
            correlation_id: 연관 ID

        Returns:
            응답 데이터

        Raises:
            TimeoutError: 응답 타임아웃
        """
        corr_id = correlation_id or str(uuid4())
        response_event_type = f"response.{corr_id}"

        # 응답 대기 Future 설정
        future: asyncio.Future = asyncio.Future()

        def response_handler(event: Event):
            if not future.done():
                future.set_result(event.data)

        self.subscribe(response_event_type, response_handler)

        try:
            # 요청 발행
            request_event = Event(
                type=f"request.{target_block}.{action}",
                source_block="EVENT_BUS",
                data=data,
                correlation_id=corr_id,
            )
            await self.publish(request_event)

            # 응답 대기
            return await asyncio.wait_for(future, timeout=timeout)

        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Request to {target_block}.{action} timed out after {timeout}s"
            )
        finally:
            self.unsubscribe(response_event_type, response_handler)

    async def respond(
        self,
        original_event: Event,
        response_data: Any,
        source_block: str,
    ) -> None:
        """
        요청에 대한 응답 발행

        Args:
            original_event: 원본 요청 이벤트
            response_data: 응답 데이터
            source_block: 응답하는 블럭 ID
        """
        if not original_event.correlation_id:
            self.logger.warning("Cannot respond: original event has no correlation_id")
            return

        response_event = Event(
            type=f"response.{original_event.correlation_id}",
            source_block=source_block,
            data=response_data,
            correlation_id=original_event.correlation_id,
        )
        await self.publish(response_event)

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        이벤트 히스토리 조회

        Args:
            event_type: 필터링할 이벤트 타입 (None이면 전체)
            limit: 반환할 최대 개수

        Returns:
            이벤트 목록 (최신순)
        """
        events = self._event_history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return list(reversed(events[-limit:]))

    def clear_history(self) -> None:
        """히스토리 초기화"""
        self._event_history.clear()

    def get_subscriber_count(self, event_type: str) -> int:
        """특정 이벤트 타입의 구독자 수"""
        return len(self._subscribers.get(event_type, []))

    def __repr__(self) -> str:
        return (
            f"EventBus(subscribers={len(self._subscribers)}, "
            f"history={len(self._event_history)})"
        )


# 글로벌 이벤트 버스 인스턴스
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """글로벌 이벤트 버스 인스턴스 반환"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
