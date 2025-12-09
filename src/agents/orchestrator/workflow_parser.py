"""
YAML 워크플로우 파서

워크플로우 정의 파일을 파싱하여 실행 가능한 구조로 변환합니다.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
import yaml


@dataclass
class WorkflowStep:
    """
    워크플로우 단계

    Attributes:
        id: 단계 고유 ID
        block_id: 실행할 블럭 ID
        action: 실행할 액션
        inputs: 입력 데이터 (${step_id.output} 형식 변수 지원)
        outputs: 출력 키 목록
        on_failure: 실패 시 동작 (abort, skip, rollback, continue)
        timeout: 타임아웃 (초)
        token_budget: 토큰 예산
        parallel: 병렬 실행 여부
        condition: 실행 조건 (표현식)
    """

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

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "id": self.id,
            "block_id": self.block_id,
            "action": self.action,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "on_failure": self.on_failure,
            "timeout": self.timeout,
            "token_budget": self.token_budget,
            "parallel": self.parallel,
            "condition": self.condition,
        }


@dataclass
class WorkflowHooks:
    """
    워크플로우 훅

    워크플로우 생명주기 이벤트에 실행되는 액션들

    Attributes:
        on_start: 워크플로우 시작 시
        on_complete: 워크플로우 완료 시
        on_error: 에러 발생 시
    """

    on_start: List[Dict[str, Any]] = field(default_factory=list)
    on_complete: List[Dict[str, Any]] = field(default_factory=list)
    on_error: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Workflow:
    """
    파싱된 워크플로우

    Attributes:
        id: 워크플로우 고유 ID
        name: 워크플로우 이름
        version: 버전
        description: 설명
        steps: 단계 목록
        hooks: 훅 설정
        context_isolation: 컨텍스트 격리 여부
        max_tokens_per_step: 단계당 최대 토큰
    """

    id: str
    name: str
    version: str = "1.0"
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)
    hooks: WorkflowHooks = field(default_factory=WorkflowHooks)
    context_isolation: bool = True
    max_tokens_per_step: int = 50000

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """단계 ID로 조회"""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "context_isolation": self.context_isolation,
            "max_tokens_per_step": self.max_tokens_per_step,
        }


class WorkflowParser:
    """
    YAML 워크플로우 파서

    워크플로우 YAML 파일을 파싱하여 Workflow 객체로 변환합니다.

    사용법:
        parser = WorkflowParser()
        workflow = parser.load("nas_sync")

        # 또는 문자열에서 파싱
        workflow = parser.parse_string(yaml_content)
    """

    DEFAULT_WORKFLOWS_DIR = Path("src/agents/workflows")

    def __init__(self, workflows_dir: Optional[Path] = None):
        """
        Args:
            workflows_dir: 워크플로우 파일 디렉토리 (기본: src/agents/workflows)
        """
        self.workflows_dir = workflows_dir or self.DEFAULT_WORKFLOWS_DIR

    def load(self, workflow_name: str) -> Workflow:
        """
        워크플로우 파일 로드 및 파싱

        Args:
            workflow_name: 워크플로우 이름 (.yaml 제외)

        Returns:
            파싱된 Workflow 객체

        Raises:
            FileNotFoundError: 워크플로우 파일이 없음
            yaml.YAMLError: YAML 파싱 오류
        """
        file_path = self.workflows_dir / f"{workflow_name}.yaml"

        if not file_path.exists():
            raise FileNotFoundError(f"Workflow not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return self._parse(data, workflow_name)

    def parse_string(self, yaml_content: str, workflow_id: str = "inline") -> Workflow:
        """
        YAML 문자열에서 워크플로우 파싱

        Args:
            yaml_content: YAML 형식 문자열
            workflow_id: 워크플로우 ID (기본: "inline")

        Returns:
            파싱된 Workflow 객체
        """
        data = yaml.safe_load(yaml_content)
        return self._parse(data, workflow_id)

    def _parse(self, data: Dict[str, Any], default_id: str) -> Workflow:
        """YAML 데이터를 Workflow 객체로 변환"""
        if not data:
            raise ValueError("Empty workflow data")

        # 단계 파싱
        steps = []
        for step_data in data.get("steps", []):
            step = WorkflowStep(
                id=step_data["id"],
                block_id=step_data["block_id"],
                action=step_data["action"],
                inputs=step_data.get("inputs", {}),
                outputs=step_data.get("outputs", []),
                on_failure=step_data.get("on_failure", "abort"),
                timeout=step_data.get("timeout"),
                token_budget=step_data.get("token_budget"),
                parallel=step_data.get("parallel", False),
                condition=step_data.get("condition"),
            )
            steps.append(step)

        # 훅 파싱
        hooks_data = data.get("hooks", {})
        hooks = WorkflowHooks(
            on_start=hooks_data.get("on_start", []),
            on_complete=hooks_data.get("on_complete", []),
            on_error=hooks_data.get("on_error", []),
        )

        # 컨텍스트 격리 설정
        context_config = data.get("context_isolation", {})
        if isinstance(context_config, bool):
            context_isolation = context_config
            max_tokens = 50000
        else:
            context_isolation = context_config.get("enabled", True)
            max_tokens = context_config.get("max_tokens_per_step", 50000)

        return Workflow(
            id=data.get("workflow_id", default_id),
            name=data.get("name", default_id),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            steps=steps,
            hooks=hooks,
            context_isolation=context_isolation,
            max_tokens_per_step=max_tokens,
        )

    def validate(self, workflow: Workflow) -> List[str]:
        """
        워크플로우 유효성 검사

        Args:
            workflow: 검사할 워크플로우

        Returns:
            에러 메시지 목록 (빈 리스트면 유효)
        """
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
                errors.append(f"Step '{step.id}' missing block_id")
            if not step.action:
                errors.append(f"Step '{step.id}' missing action")

            # on_failure 값 검증
            valid_failures = {"abort", "skip", "rollback", "continue"}
            if step.on_failure not in valid_failures:
                errors.append(
                    f"Step '{step.id}' has invalid on_failure: {step.on_failure}"
                )

        # 변수 참조 검증
        for step in workflow.steps:
            for key, value in step.inputs.items():
                if isinstance(value, str) and value.startswith("${"):
                    ref_step_id = value[2:].split(".")[0]
                    if ref_step_id not in step_ids:
                        errors.append(
                            f"Step '{step.id}' references unknown step: {ref_step_id}"
                        )

        return errors

    def list_workflows(self) -> List[str]:
        """
        사용 가능한 워크플로우 목록

        Returns:
            워크플로우 이름 목록
        """
        if not self.workflows_dir.exists():
            return []

        return [
            f.stem
            for f in self.workflows_dir.glob("*.yaml")
            if f.is_file()
        ]
