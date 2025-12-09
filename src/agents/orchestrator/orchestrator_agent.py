"""
OrchestratorAgent - 중앙 조율 에이전트

워크플로우 실행 및 블럭 에이전트 조율을 담당합니다.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from uuid import uuid4
import asyncio
import logging

from ..core.base_agent import BaseAgent, AgentState
from ..core.agent_context import AgentContext, WorkflowContext
from ..core.agent_result import AgentResult
from ..core.agent_registry import AgentRegistry, get_registry
from ..core.event_bus import EventBus, Event, get_event_bus
from ..core.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry
from ..core.exceptions import (
    AgentNotFoundError,
    CapabilityNotFoundError,
    CircuitBreakerOpenError,
    WorkflowError,
    WorkflowNotFoundError,
)
from .workflow_parser import WorkflowParser, Workflow, WorkflowStep


@dataclass
class OrchestratorConfig:
    """Orchestrator 설정"""

    max_concurrent_workflows: int = 5
    default_timeout: int = 300
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60


class OrchestratorAgent:
    """
    중앙 조율 에이전트

    개발자(지휘자)의 명령을 받아 적절한 블럭 에이전트에게
    작업을 분배하고 워크플로우를 관리합니다.

    핵심 책임:
    1. 워크플로우 파싱 및 실행
    2. 블럭 에이전트 선택 및 디스패치
    3. 블럭 간 데이터 전달
    4. 에러 처리 및 롤백
    5. 전역 상태 관리

    Example:
        orchestrator = OrchestratorAgent()

        # 워크플로우 실행
        result = await orchestrator.execute_workflow("nas_sync")

        # 직접 디스패치
        result = await orchestrator.dispatch(
            command="parse_filename",
            target_block="BLOCK_PARSER",
            params={"filename": "test.mp4"}
        )
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.block_id = "ORCHESTRATOR"
        self.config = config or OrchestratorConfig()
        self.state = AgentState.IDLE
        self.logger = logging.getLogger("agent.orchestrator")

        # 컴포넌트 초기화
        self.registry: AgentRegistry = get_registry()
        self.event_bus: EventBus = get_event_bus()
        self.workflow_parser = WorkflowParser()
        self.circuit_breakers = CircuitBreakerRegistry(
            default_failure_threshold=self.config.circuit_breaker_threshold,
            default_recovery_timeout=self.config.circuit_breaker_timeout,
        )

        # 활성 워크플로우 추적
        self._active_workflows: Dict[str, WorkflowContext] = {}

        # 메트릭
        self._metrics: Dict[str, Any] = {
            "workflows_executed": 0,
            "workflows_succeeded": 0,
            "workflows_failed": 0,
            "dispatches_total": 0,
        }

    # ─────────────────────────────────────────────────────────────────
    # 워크플로우 실행
    # ─────────────────────────────────────────────────────────────────

    async def execute_workflow(
        self,
        workflow_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        YAML 워크플로우 실행

        Args:
            workflow_name: 워크플로우 이름 (파일명에서 .yaml 제외)
            params: 워크플로우 초기 파라미터

        Returns:
            AgentResult: 전체 워크플로우 실행 결과

        Example:
            result = await orchestrator.execute_workflow(
                "nas_sync",
                params={"path": "/ARCHIVE/WSOP"}
            )
        """
        self.logger.info(f"Starting workflow: {workflow_name}")
        self._metrics["workflows_executed"] += 1

        # 1. 워크플로우 로드 및 파싱
        try:
            workflow = self.workflow_parser.load(workflow_name)
        except FileNotFoundError:
            self._metrics["workflows_failed"] += 1
            return AgentResult.failure_result(
                f"Workflow not found: {workflow_name}",
                error_type="WorkflowNotFoundError",
            )
        except Exception as e:
            self._metrics["workflows_failed"] += 1
            return AgentResult.failure_result(
                f"Failed to parse workflow: {e}",
                error_type="WorkflowParseError",
            )

        # 워크플로우 검증
        validation_errors = self.workflow_parser.validate(workflow)
        if validation_errors:
            self._metrics["workflows_failed"] += 1
            return AgentResult.failure_result(
                f"Workflow validation failed: {validation_errors}",
                error_type="WorkflowValidationError",
            )

        # 2. 워크플로우 컨텍스트 생성
        wf_context = WorkflowContext(
            workflow_name=workflow_name,
            total_steps=len(workflow.steps),
        )
        wf_context.start()
        self._active_workflows[wf_context.workflow_id] = wf_context

        # 3. 초기 데이터 설정
        if params:
            wf_context.accumulated_data.update(params)

        # 4. 훅 실행 (on_start)
        await self._execute_hooks(workflow.hooks.on_start, wf_context)

        # 5. 단계별 실행
        try:
            for i, step in enumerate(workflow.steps):
                wf_context.current_step = i + 1

                # 조건 체크
                if step.condition and not self._evaluate_condition(
                    step.condition, wf_context
                ):
                    self.logger.info(f"Skipping step {step.id} (condition not met)")
                    continue

                # 단계 실행
                step_result = await self._execute_step(
                    step=step,
                    workflow_context=wf_context,
                    max_tokens=workflow.max_tokens_per_step,
                )

                # 결과 저장
                wf_context.save_step_result(step.id, step_result)

                # 출력을 다음 단계 입력으로
                if step_result.success and step_result.data:
                    if isinstance(step_result.data, dict):
                        for output_key in step.outputs:
                            if output_key in step_result.data:
                                key = f"{step.id}.{output_key}"
                                wf_context.accumulated_data[key] = step_result.data[
                                    output_key
                                ]

                # 실패 처리
                if not step_result.success:
                    wf_context.add_error(
                        f"Step {step.id} failed: {step_result.first_error}"
                    )

                    if step.on_failure == "abort":
                        wf_context.complete(success=False)
                        await self._execute_hooks(workflow.hooks.on_error, wf_context)
                        self._metrics["workflows_failed"] += 1
                        return AgentResult.failure_result(
                            f"Workflow aborted at step {step.id}",
                            error_type="WorkflowAbortedError",
                        )

                    elif step.on_failure == "rollback":
                        await self._rollback_workflow(wf_context, step)
                        await self._execute_hooks(workflow.hooks.on_error, wf_context)
                        self._metrics["workflows_failed"] += 1
                        return AgentResult.failure_result(
                            f"Workflow rolled back at step {step.id}",
                            error_type="WorkflowRollbackError",
                        )
                    # skip, continue: 계속 진행

                # 이벤트 발행
                await self.event_bus.publish(
                    Event(
                        type="workflow.step.completed",
                        source_block=self.block_id,
                        data={
                            "workflow_id": wf_context.workflow_id,
                            "step_id": step.id,
                            "success": step_result.success,
                        },
                    )
                )

            # 6. 완료
            wf_context.complete(success=True)
            await self._execute_hooks(workflow.hooks.on_complete, wf_context)
            self._metrics["workflows_succeeded"] += 1

            return AgentResult.success_result(
                data={
                    "workflow_id": wf_context.workflow_id,
                    "accumulated_data": wf_context.accumulated_data,
                    "step_results": {
                        k: v.to_dict() if hasattr(v, "to_dict") else v
                        for k, v in wf_context.step_results.items()
                    },
                },
                metrics={
                    "total_steps": wf_context.total_steps,
                    "duration_seconds": wf_context.duration_seconds or 0,
                },
            )

        except Exception as e:
            wf_context.complete(success=False)
            wf_context.add_error(str(e))
            await self._execute_hooks(workflow.hooks.on_error, wf_context)
            self._metrics["workflows_failed"] += 1
            self.logger.error(f"Workflow error: {e}", exc_info=True)
            return AgentResult.failure_result(str(e), error_type=type(e).__name__)

        finally:
            # 정리
            self._active_workflows.pop(wf_context.workflow_id, None)

    async def _execute_step(
        self,
        step: WorkflowStep,
        workflow_context: WorkflowContext,
        max_tokens: int,
    ) -> AgentResult:
        """워크플로우 단계 실행"""
        self.logger.info(f"Executing step: {step.id} -> {step.block_id}.{step.action}")

        # Circuit Breaker 체크
        if self.config.enable_circuit_breaker:
            cb = self.circuit_breakers.get_or_create(step.block_id)
            if not cb.can_execute():
                return AgentResult.failure_result(
                    f"Circuit breaker open for {step.block_id}",
                    error_type="CircuitBreakerOpenError",
                )

        # 에이전트 조회
        agent = self.registry.get_agent_safe(step.block_id)
        if agent is None:
            return AgentResult.failure_result(
                f"Agent not found: {step.block_id}",
                error_type="AgentNotFoundError",
            )

        # 입력 데이터 준비 (변수 치환)
        input_data = self._resolve_inputs(step.inputs, workflow_context)
        input_data["command"] = step.action

        # 컨텍스트 생성
        context = AgentContext(
            workflow_id=workflow_context.workflow_id,
            step_id=step.id,
            timeout_seconds=step.timeout or self.config.default_timeout,
            estimated_tokens=step.token_budget or max_tokens,
            input_from_previous=input_data,
        )

        # 실행 (타임아웃 적용)
        try:
            result = await asyncio.wait_for(
                agent.execute(context, input_data),
                timeout=context.timeout_seconds,
            )

            # Circuit Breaker 업데이트
            if self.config.enable_circuit_breaker:
                cb = self.circuit_breakers.get_or_create(step.block_id)
                if result.success:
                    cb.record_success()
                else:
                    cb.record_failure()

            return result

        except asyncio.TimeoutError:
            if self.config.enable_circuit_breaker:
                self.circuit_breakers.get_or_create(step.block_id).record_failure()
            return AgentResult.failure_result(
                f"Step {step.id} timed out after {context.timeout_seconds}s",
                error_type="TimeoutError",
            )
        except Exception as e:
            if self.config.enable_circuit_breaker:
                self.circuit_breakers.get_or_create(step.block_id).record_failure()
            return AgentResult.failure_result(str(e), error_type=type(e).__name__)

    def _resolve_inputs(
        self,
        inputs: Dict[str, Any],
        workflow_context: WorkflowContext,
    ) -> Dict[str, Any]:
        """입력 값 해석 (변수 치환)"""
        resolved = {}

        for key, value in inputs.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # 변수 참조: ${step_id.output_key}
                var_path = value[2:-1]
                resolved[key] = workflow_context.accumulated_data.get(var_path)
            elif isinstance(value, dict):
                # 중첩된 딕셔너리 처리
                resolved[key] = self._resolve_inputs(value, workflow_context)
            else:
                resolved[key] = value

        return resolved

    def _evaluate_condition(
        self, condition: str, workflow_context: WorkflowContext
    ) -> bool:
        """조건 평가 (간단한 표현식)"""
        # 간단한 구현: 변수 존재 여부 체크
        # 예: "${scan_files.files}" -> files가 있으면 True
        if condition.startswith("${") and condition.endswith("}"):
            var_path = condition[2:-1]
            value = workflow_context.accumulated_data.get(var_path)
            return value is not None and (
                not isinstance(value, (list, dict)) or len(value) > 0
            )
        return True

    async def _execute_hooks(
        self, hooks: List[Dict[str, Any]], workflow_context: WorkflowContext
    ) -> None:
        """훅 실행"""
        for hook in hooks:
            if "log" in hook:
                message = self._resolve_string(hook["log"], workflow_context)
                self.logger.info(f"[Hook] {message}")
            elif "notify" in hook:
                # 알림 훅 (확장 가능)
                await self.event_bus.publish(
                    Event(
                        type="workflow.notification",
                        source_block=self.block_id,
                        data=hook["notify"],
                    )
                )

    def _resolve_string(self, template: str, workflow_context: WorkflowContext) -> str:
        """문자열 내 변수 치환"""
        import re

        def replace_var(match):
            var_path = match.group(1)
            value = workflow_context.accumulated_data.get(var_path, f"${{{var_path}}}")
            return str(value)

        return re.sub(r"\$\{([^}]+)\}", replace_var, template)

    async def _rollback_workflow(
        self, workflow_context: WorkflowContext, failed_step: WorkflowStep
    ) -> None:
        """워크플로우 롤백"""
        self.logger.warning(f"Rolling back workflow: {workflow_context.workflow_id}")

        # 롤백 이벤트 발행
        await self.event_bus.publish(
            Event(
                type="workflow.rollback",
                source_block=self.block_id,
                data={
                    "workflow_id": workflow_context.workflow_id,
                    "failed_step": failed_step.id,
                },
            )
        )

    # ─────────────────────────────────────────────────────────────────
    # 직접 디스패치
    # ─────────────────────────────────────────────────────────────────

    async def dispatch(
        self,
        command: str,
        target_block: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        특정 블럭에 직접 명령 전달

        워크플로우 없이 단일 블럭에 작업을 요청할 때 사용합니다.

        Args:
            command: 명령어 (에이전트의 capability와 매칭)
            target_block: 대상 블럭 ID
            params: 명령 파라미터

        Returns:
            AgentResult: 실행 결과

        Example:
            result = await orchestrator.dispatch(
                command="parse_filename",
                target_block="BLOCK_PARSER",
                params={"filename": "10-wsop-2024-be-ev-21.mp4"}
            )
        """
        self.logger.info(f"Dispatching: {command} -> {target_block}")
        self._metrics["dispatches_total"] += 1

        # Circuit Breaker 체크
        if self.config.enable_circuit_breaker:
            cb = self.circuit_breakers.get_or_create(target_block)
            if not cb.can_execute():
                return AgentResult.failure_result(
                    f"Circuit breaker open for {target_block}",
                    error_type="CircuitBreakerOpenError",
                )

        # 에이전트 조회
        agent = self.registry.get_agent_safe(target_block)
        if agent is None:
            return AgentResult.failure_result(
                f"Agent not found: {target_block}",
                error_type="AgentNotFoundError",
            )

        # 능력 체크
        if command not in agent.get_capabilities():
            return AgentResult.failure_result(
                f"Agent {target_block} does not have capability: {command}",
                error_type="CapabilityNotFoundError",
            )

        # 컨텍스트 생성
        context = AgentContext(timeout_seconds=self.config.default_timeout)

        # 입력 데이터
        input_data = {"command": command, **(params or {})}

        # 실행
        try:
            result = await agent.execute(context, input_data)

            # Circuit Breaker 업데이트
            if self.config.enable_circuit_breaker:
                cb = self.circuit_breakers.get_or_create(target_block)
                if result.success:
                    cb.record_success()
                else:
                    cb.record_failure()

            return result

        except Exception as e:
            if self.config.enable_circuit_breaker:
                self.circuit_breakers.get_or_create(target_block).record_failure()
            return AgentResult.failure_result(str(e), error_type=type(e).__name__)

    async def dispatch_parallel(
        self, tasks: List[Dict[str, Any]]
    ) -> List[AgentResult]:
        """
        여러 블럭에 병렬 디스패치

        Args:
            tasks: [{"command": str, "target_block": str, "params": dict}, ...]

        Returns:
            각 태스크의 결과 목록
        """
        coroutines = [
            self.dispatch(
                command=task["command"],
                target_block=task["target_block"],
                params=task.get("params", {}),
            )
            for task in tasks
        ]

        results = await asyncio.gather(*coroutines, return_exceptions=True)

        # 예외를 AgentResult로 변환
        return [
            (
                r
                if isinstance(r, AgentResult)
                else AgentResult.failure_result(str(r), error_type=type(r).__name__)
            )
            for r in results
        ]

    # ─────────────────────────────────────────────────────────────────
    # 상태 조회
    # ─────────────────────────────────────────────────────────────────

    def get_active_workflows(self) -> List[Dict]:
        """활성 워크플로우 목록"""
        return [wf.to_dict() for wf in self._active_workflows.values()]

    def get_circuit_breaker_status(self) -> Dict[str, Dict]:
        """블럭별 Circuit Breaker 상태"""
        return self.circuit_breakers.get_all_stats()

    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 조회"""
        return self._metrics.copy()

    def get_registered_agents(self) -> List[str]:
        """등록된 에이전트 목록"""
        return self.registry.list_agents()

    def __repr__(self) -> str:
        return (
            f"OrchestratorAgent(agents={len(self.registry)}, "
            f"active_workflows={len(self._active_workflows)})"
        )
