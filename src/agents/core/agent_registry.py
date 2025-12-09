"""
에이전트 중앙 등록소 (싱글톤)

모든 블럭 에이전트를 등록하고 조회하는 중앙 관리자입니다.
"""

from typing import TYPE_CHECKING, Dict, List, Optional
from threading import Lock
import logging

if TYPE_CHECKING:
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

    Note:
        싱글톤 패턴을 사용하므로 여러 번 인스턴스화해도
        동일한 인스턴스가 반환됩니다.
    """

    _instance: Optional["AgentRegistry"] = None
    _lock: Lock = Lock()

    def __new__(cls) -> "AgentRegistry":
        """싱글톤 패턴"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._agents: Dict[str, "BaseAgent"] = {}
        self._capabilities_index: Dict[str, List[str]] = {}  # capability -> [block_ids]
        self.logger = logging.getLogger("agent.registry")
        self._initialized = True

    def register(self, agent: "BaseAgent") -> None:
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

        self.logger.info(
            f"Registered agent: {agent.block_id} "
            f"(capabilities: {agent.get_capabilities()})"
        )

    def unregister(self, block_id: str) -> bool:
        """
        에이전트 등록 해제

        Args:
            block_id: 해제할 블럭 ID

        Returns:
            True if 해제됨, False if 존재하지 않음
        """
        if block_id not in self._agents:
            return False

        agent = self._agents.pop(block_id)

        # 능력 인덱스에서 제거
        for capability in agent.get_capabilities():
            if capability in self._capabilities_index:
                if block_id in self._capabilities_index[capability]:
                    self._capabilities_index[capability].remove(block_id)
                # 빈 리스트 정리
                if not self._capabilities_index[capability]:
                    del self._capabilities_index[capability]

        self.logger.info(f"Unregistered agent: {block_id}")
        return True

    def get_agent(self, block_id: str) -> "BaseAgent":
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

    def get_agent_safe(self, block_id: str) -> Optional["BaseAgent"]:
        """
        에이전트 조회 (안전 버전)

        Args:
            block_id: 블럭 ID

        Returns:
            등록된 에이전트 또는 None
        """
        return self._agents.get(block_id)

    def find_by_capability(self, capability: str) -> List["BaseAgent"]:
        """
        능력으로 에이전트 검색

        Args:
            capability: 찾을 능력

        Returns:
            해당 능력을 가진 에이전트 목록
        """
        block_ids = self._capabilities_index.get(capability, [])
        return [self._agents[bid] for bid in block_ids if bid in self._agents]

    def has_capability(self, capability: str) -> bool:
        """특정 능력을 가진 에이전트가 있는지 확인"""
        return capability in self._capabilities_index and bool(
            self._capabilities_index[capability]
        )

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
        """
        모든 에이전트 등록 해제 (테스트용)

        Warning:
            프로덕션에서는 사용하지 마세요.
        """
        self._agents.clear()
        self._capabilities_index.clear()
        self.logger.warning("Registry cleared - all agents unregistered")

    def __contains__(self, block_id: str) -> bool:
        """in 연산자 지원"""
        return block_id in self._agents

    def __len__(self) -> int:
        """len() 지원"""
        return len(self._agents)

    def __iter__(self):
        """이터레이션 지원"""
        return iter(self._agents.values())


# 글로벌 인스턴스
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """
    글로벌 레지스트리 인스턴스 반환

    Returns:
        AgentRegistry 싱글톤 인스턴스
    """
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def reset_registry() -> None:
    """
    레지스트리 초기화 (테스트용)

    Warning:
        프로덕션에서는 사용하지 마세요.
    """
    global _registry
    if _registry is not None:
        _registry.clear()
    _registry = None
