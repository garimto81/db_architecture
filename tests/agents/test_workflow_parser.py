"""
WorkflowParser 테스트

YAML 워크플로우 파싱을 테스트합니다.
"""

import pytest
from pathlib import Path

from src.agents.orchestrator.workflow_parser import (
    WorkflowParser,
    Workflow,
    WorkflowStep,
    WorkflowHooks,
)


@pytest.fixture
def parser():
    """WorkflowParser 픽스처"""
    return WorkflowParser(
        workflows_dir=Path("src/agents/workflows")
    )


@pytest.fixture
def sample_yaml():
    """샘플 YAML 워크플로우"""
    return """
workflow_id: test_workflow
name: 테스트 워크플로우
version: "1.0"
description: 테스트용 워크플로우

context_isolation:
  enabled: true
  max_tokens_per_step: 30000

steps:
  - id: step1
    block_id: BLOCK_PARSER
    action: parse_filename
    inputs:
      filename: "${params.filename}"
    outputs:
      - parsed_data
    on_failure: abort
    timeout: 60

  - id: step2
    block_id: BLOCK_STORAGE
    action: save_record
    inputs:
      table: video_files
      data: "${step1.parsed_data}"
    on_failure: rollback
    condition: "${step1.success}"

hooks:
  on_start:
    - action: log
      message: "시작"
  on_complete:
    - action: notify
      message: "완료"
  on_error:
    - action: notify
      message: "에러 발생"
"""


class TestWorkflowParser:
    """WorkflowParser 테스트"""

    def test_parse_string(self, parser, sample_yaml):
        """문자열 파싱 테스트"""
        workflow = parser.parse_string(sample_yaml, "test_workflow")

        assert workflow.id == "test_workflow"
        assert workflow.name == "테스트 워크플로우"
        assert workflow.version == "1.0"
        assert len(workflow.steps) == 2

    def test_parse_steps(self, parser, sample_yaml):
        """단계 파싱 테스트"""
        workflow = parser.parse_string(sample_yaml)

        step1 = workflow.get_step("step1")
        assert step1 is not None
        assert step1.block_id == "BLOCK_PARSER"
        assert step1.action == "parse_filename"
        assert step1.on_failure == "abort"
        assert step1.timeout == 60

        step2 = workflow.get_step("step2")
        assert step2 is not None
        assert step2.block_id == "BLOCK_STORAGE"
        assert step2.condition == "${step1.success}"

    def test_parse_hooks(self, parser, sample_yaml):
        """훅 파싱 테스트"""
        workflow = parser.parse_string(sample_yaml)

        assert len(workflow.hooks.on_start) == 1
        assert len(workflow.hooks.on_complete) == 1
        assert len(workflow.hooks.on_error) == 1

        assert workflow.hooks.on_start[0]["action"] == "log"

    def test_parse_context_isolation(self, parser, sample_yaml):
        """컨텍스트 격리 설정 파싱 테스트"""
        workflow = parser.parse_string(sample_yaml)

        assert workflow.context_isolation is True
        assert workflow.max_tokens_per_step == 30000

    def test_validate_workflow(self, parser, sample_yaml):
        """워크플로우 유효성 검사 테스트"""
        workflow = parser.parse_string(sample_yaml)
        errors = parser.validate(workflow)

        assert len(errors) == 0

    def test_validate_duplicate_step_ids(self, parser):
        """중복 단계 ID 검증 테스트"""
        yaml_with_duplicates = """
steps:
  - id: step1
    block_id: BLOCK_A
    action: test
  - id: step1
    block_id: BLOCK_B
    action: test
"""
        workflow = parser.parse_string(yaml_with_duplicates)
        errors = parser.validate(workflow)

        assert any("Duplicate step ID" in e for e in errors)

    def test_validate_missing_block_id(self, parser):
        """누락된 block_id 검증 테스트"""
        yaml_missing_block = """
steps:
  - id: step1
    action: test
"""
        workflow = parser.parse_string(yaml_missing_block)
        errors = parser.validate(workflow)

        assert any("missing block_id" in e for e in errors)

    def test_validate_invalid_on_failure(self, parser):
        """잘못된 on_failure 검증 테스트"""
        yaml_invalid = """
steps:
  - id: step1
    block_id: BLOCK_A
    action: test
    on_failure: invalid_value
"""
        workflow = parser.parse_string(yaml_invalid)
        errors = parser.validate(workflow)

        assert any("invalid on_failure" in e for e in errors)

    def test_validate_unknown_step_reference(self, parser):
        """존재하지 않는 단계 참조 검증 테스트"""
        yaml_bad_ref = """
steps:
  - id: step1
    block_id: BLOCK_A
    action: test
    inputs:
      data: "${unknown_step.output}"
"""
        workflow = parser.parse_string(yaml_bad_ref)
        errors = parser.validate(workflow)

        assert any("unknown step" in e for e in errors)

    def test_empty_workflow_validation(self, parser):
        """빈 워크플로우 검증 테스트"""
        yaml_empty = "steps: []"
        workflow = parser.parse_string(yaml_empty)
        errors = parser.validate(workflow)

        assert any("no steps" in e.lower() for e in errors)

    def test_load_nas_sync_workflow(self, parser):
        """nas_sync 워크플로우 로드 테스트"""
        try:
            workflow = parser.load("nas_sync")

            assert workflow.id == "nas_sync"
            assert len(workflow.steps) > 0

            # 첫 번째 단계가 scan_nas인지 확인
            first_step = workflow.steps[0]
            assert first_step.block_id == "BLOCK_SYNC"
            assert first_step.action == "scan_nas"

        except FileNotFoundError:
            pytest.skip("nas_sync.yaml not found")

    def test_list_workflows(self, parser):
        """워크플로우 목록 조회 테스트"""
        workflows = parser.list_workflows()

        # workflows 디렉토리가 있다면 yaml 파일 목록 반환
        assert isinstance(workflows, list)


class TestWorkflowStep:
    """WorkflowStep 테스트"""

    def test_step_to_dict(self):
        """단계 딕셔너리 변환 테스트"""
        step = WorkflowStep(
            id="test_step",
            block_id="BLOCK_TEST",
            action="test_action",
            inputs={"key": "value"},
            outputs=["result"],
            on_failure="abort",
            timeout=60,
        )

        d = step.to_dict()

        assert d["id"] == "test_step"
        assert d["block_id"] == "BLOCK_TEST"
        assert d["inputs"]["key"] == "value"
        assert d["timeout"] == 60


class TestWorkflow:
    """Workflow 테스트"""

    def test_workflow_get_step(self):
        """워크플로우 단계 조회 테스트"""
        workflow = Workflow(
            id="test",
            name="Test Workflow",
            steps=[
                WorkflowStep(id="step1", block_id="BLOCK_A", action="action_a"),
                WorkflowStep(id="step2", block_id="BLOCK_B", action="action_b"),
            ],
        )

        step1 = workflow.get_step("step1")
        assert step1 is not None
        assert step1.block_id == "BLOCK_A"

        nonexistent = workflow.get_step("step999")
        assert nonexistent is None

    def test_workflow_to_dict(self):
        """워크플로우 딕셔너리 변환 테스트"""
        workflow = Workflow(
            id="test",
            name="Test Workflow",
            version="2.0",
            steps=[
                WorkflowStep(id="step1", block_id="BLOCK_A", action="action_a"),
            ],
        )

        d = workflow.to_dict()

        assert d["id"] == "test"
        assert d["name"] == "Test Workflow"
        assert d["version"] == "2.0"
        assert len(d["steps"]) == 1
