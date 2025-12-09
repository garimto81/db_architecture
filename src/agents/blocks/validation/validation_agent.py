"""
ValidationAgent - 데이터 검증 전담 에이전트

데이터 무결성 및 일관성 검증을 담당합니다.

주요 기능:
- 레코드 스키마 검증
- 파일 존재 검증
- 데이터 일관성 체크
- 검증 리포트 생성
"""

import os
import re
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime
import sqlite3
from contextlib import contextmanager

from ...core.base_agent import BaseAgent
from ...core.agent_context import AgentContext
from ...core.agent_result import AgentResult
from ...core.exceptions import AgentExecutionError


class ValidationSeverity(Enum):
    """검증 심각도"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """검증 이슈"""

    code: str
    message: str
    severity: ValidationSeverity
    field: Optional[str] = None
    record_id: Optional[str] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "field": self.field,
            "record_id": self.record_id,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationReport:
    """검증 리포트"""

    passed: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    errors: int = 0
    warnings: int = 0
    checked_items: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def add_issue(self, issue: ValidationIssue) -> None:
        """이슈 추가"""
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR:
            self.errors += 1
            self.passed = False
        elif issue.severity == ValidationSeverity.WARNING:
            self.warnings += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [i.to_dict() for i in self.issues],
            "errors": self.errors,
            "warnings": self.warnings,
            "checked_items": self.checked_items,
            "timestamp": self.timestamp.isoformat(),
        }


# 스키마 정의
RECORD_SCHEMAS = {
    "video_files": {
        "required": ["filename"],
        "optional": ["project", "year", "event_name", "stage", "part", "path", "size"],
        "types": {
            "filename": str,
            "project": str,
            "year": int,
            "event_name": str,
            "stage": str,
            "part": int,
            "size": int,
        },
        "constraints": {
            "year": {"min": 2000, "max": 2030},
            "part": {"min": 1, "max": 100},
            "size": {"min": 0},
        },
        "patterns": {
            "filename": r".+\.(mp4|mkv|avi|mov|wmv|m4v)$",
        },
    },
    "projects": {
        "required": ["name"],
        "optional": ["description", "start_year", "end_year"],
        "types": {
            "name": str,
            "description": str,
            "start_year": int,
            "end_year": int,
        },
    },
}


class ValidationAgent(BaseAgent):
    """
    데이터 검증 전담 에이전트

    데이터 무결성과 일관성을 검증합니다.

    사용법:
        agent = ValidationAgent(config={"db_path": "pokervod.db"})
        result = await agent.execute(context, {
            "action": "validate_record",
            "schema": "video_files",
            "data": {"filename": "test.mp4", "year": 2023}
        })

    Capabilities:
        - validate_record: 단일 레코드 검증
        - validate_batch: 다중 레코드 검증
        - validate_file: 파일 존재 검증
        - check_consistency: 데이터 일관성 체크
        - check_orphans: 고아 레코드 검색
        - generate_report: 검증 리포트 생성
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 에이전트 설정
                - db_path: 데이터베이스 경로
                - strict_mode: 엄격 모드 (경고도 에러로)
                - file_check_enabled: 파일 존재 체크 활성화
        """
        super().__init__("BLOCK_VALIDATION", config)

        self._db_path = self.config.get("db_path", "")
        self._strict_mode = self.config.get("strict_mode", False)
        self._file_check_enabled = self.config.get("file_check_enabled", True)
        self._schemas = RECORD_SCHEMAS.copy()

    def get_capabilities(self) -> List[str]:
        """에이전트 능력 목록"""
        return [
            "validate_record",
            "validate_batch",
            "validate_file",
            "check_consistency",
            "check_orphans",
            "generate_report",
        ]

    @contextmanager
    def _get_connection(self):
        """데이터베이스 연결"""
        if not self._db_path:
            raise AgentExecutionError("db_path is not configured", self.block_id)

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row

        try:
            yield conn
        finally:
            conn.close()

    async def execute(
        self, context: AgentContext, input_data: Dict[str, Any]
    ) -> AgentResult:
        """
        메인 실행 로직

        Args:
            context: 실행 컨텍스트
            input_data: 입력 데이터

        Returns:
            AgentResult: 검증 결과
        """
        try:
            await self.pre_execute(context)

            action = input_data.get("action", "validate_record")

            if action == "validate_record":
                result = await self._validate_record(input_data)
            elif action == "validate_batch":
                result = await self._validate_batch(input_data)
            elif action == "validate_file":
                result = await self._validate_file(input_data)
            elif action == "check_consistency":
                result = await self._check_consistency(input_data)
            elif action == "check_orphans":
                result = await self._check_orphans(input_data)
            elif action == "generate_report":
                result = await self._generate_report(input_data)
            else:
                raise AgentExecutionError(
                    f"Unknown action: {action}", self.block_id
                )

            await self.post_execute(result)
            return result

        except Exception as e:
            return await self.handle_error(e, context)

    async def _validate_record(self, input_data: Dict[str, Any]) -> AgentResult:
        """단일 레코드 검증"""
        schema_name = input_data.get("schema", "video_files")
        data = input_data.get("data", {})
        record_id = input_data.get("record_id")

        if schema_name not in self._schemas:
            return AgentResult.failure_result(
                errors=[f"Unknown schema: {schema_name}"],
                error_type="ValidationError",
            )

        schema = self._schemas[schema_name]
        report = ValidationReport(checked_items=1)

        self._track_tokens(self._estimate_tokens(str(data)))

        # 필수 필드 체크
        for required_field in schema.get("required", []):
            if required_field not in data or data[required_field] is None:
                report.add_issue(
                    ValidationIssue(
                        code="MISSING_REQUIRED_FIELD",
                        message=f"Required field '{required_field}' is missing",
                        severity=ValidationSeverity.ERROR,
                        field=required_field,
                        record_id=record_id,
                        suggestion=f"Add '{required_field}' field to the record",
                    )
                )

        # 타입 체크
        types = schema.get("types", {})
        for field_name, expected_type in types.items():
            if field_name in data and data[field_name] is not None:
                if not isinstance(data[field_name], expected_type):
                    report.add_issue(
                        ValidationIssue(
                            code="TYPE_MISMATCH",
                            message=f"Field '{field_name}' should be {expected_type.__name__}, got {type(data[field_name]).__name__}",
                            severity=ValidationSeverity.ERROR,
                            field=field_name,
                            record_id=record_id,
                        )
                    )

        # 제약 조건 체크
        constraints = schema.get("constraints", {})
        for field_name, constraint in constraints.items():
            if field_name in data and data[field_name] is not None:
                value = data[field_name]
                if "min" in constraint and value < constraint["min"]:
                    report.add_issue(
                        ValidationIssue(
                            code="VALUE_TOO_SMALL",
                            message=f"Field '{field_name}' value {value} is below minimum {constraint['min']}",
                            severity=ValidationSeverity.ERROR,
                            field=field_name,
                            record_id=record_id,
                        )
                    )
                if "max" in constraint and value > constraint["max"]:
                    report.add_issue(
                        ValidationIssue(
                            code="VALUE_TOO_LARGE",
                            message=f"Field '{field_name}' value {value} exceeds maximum {constraint['max']}",
                            severity=ValidationSeverity.ERROR,
                            field=field_name,
                            record_id=record_id,
                        )
                    )

        # 패턴 체크
        patterns = schema.get("patterns", {})
        for field_name, pattern in patterns.items():
            if field_name in data and data[field_name] is not None:
                if not re.match(pattern, str(data[field_name]), re.IGNORECASE):
                    report.add_issue(
                        ValidationIssue(
                            code="PATTERN_MISMATCH",
                            message=f"Field '{field_name}' does not match pattern: {pattern}",
                            severity=ValidationSeverity.WARNING,
                            field=field_name,
                            record_id=record_id,
                        )
                    )

        return AgentResult.success_result(
            data=report.to_dict(),
            metrics={"errors": report.errors, "warnings": report.warnings},
        )

    async def _validate_batch(self, input_data: Dict[str, Any]) -> AgentResult:
        """다중 레코드 검증"""
        schema_name = input_data.get("schema", "video_files")
        records = input_data.get("records", [])

        if not records:
            return AgentResult.failure_result(
                errors=["records list is required"],
                error_type="ValidationError",
            )

        combined_report = ValidationReport(checked_items=len(records))

        for i, record in enumerate(records):
            result = await self._validate_record({
                "schema": schema_name,
                "data": record,
                "record_id": record.get("id", str(i)),
            })

            if result.data:
                for issue_data in result.data.get("issues", []):
                    issue = ValidationIssue(
                        code=issue_data["code"],
                        message=issue_data["message"],
                        severity=ValidationSeverity(issue_data["severity"]),
                        field=issue_data.get("field"),
                        record_id=issue_data.get("record_id"),
                        suggestion=issue_data.get("suggestion"),
                    )
                    combined_report.add_issue(issue)

        return AgentResult.success_result(
            data=combined_report.to_dict(),
            metrics={
                "total_records": len(records),
                "errors": combined_report.errors,
                "warnings": combined_report.warnings,
            },
        )

    async def _validate_file(self, input_data: Dict[str, Any]) -> AgentResult:
        """파일 존재 검증"""
        file_path = input_data.get("path", "")
        paths = input_data.get("paths", [])

        report = ValidationReport()

        if file_path:
            paths = [file_path]

        report.checked_items = len(paths)

        for path in paths:
            self._track_tokens(10)  # 파일 체크당 토큰

            if not path:
                continue

            path_obj = Path(path)
            if not path_obj.exists():
                report.add_issue(
                    ValidationIssue(
                        code="FILE_NOT_FOUND",
                        message=f"File does not exist: {path}",
                        severity=ValidationSeverity.ERROR,
                        record_id=path,
                        suggestion="Check file path or sync from source",
                    )
                )
            elif not path_obj.is_file():
                report.add_issue(
                    ValidationIssue(
                        code="NOT_A_FILE",
                        message=f"Path is not a file: {path}",
                        severity=ValidationSeverity.ERROR,
                        record_id=path,
                    )
                )
            elif path_obj.stat().st_size == 0:
                report.add_issue(
                    ValidationIssue(
                        code="EMPTY_FILE",
                        message=f"File is empty: {path}",
                        severity=ValidationSeverity.WARNING,
                        record_id=path,
                    )
                )

        return AgentResult.success_result(
            data=report.to_dict(),
            metrics={
                "files_checked": report.checked_items,
                "missing": report.errors,
            },
        )

    async def _check_consistency(self, input_data: Dict[str, Any]) -> AgentResult:
        """데이터 일관성 체크"""
        checks = input_data.get("checks", ["duplicates", "nulls", "references"])

        report = ValidationReport()

        with self._get_connection() as conn:
            if "duplicates" in checks:
                # 중복 파일명 체크
                cursor = conn.execute(
                    """
                    SELECT filename, COUNT(*) as cnt
                    FROM video_files
                    GROUP BY filename
                    HAVING cnt > 1
                    """
                )
                duplicates = cursor.fetchall()
                report.checked_items += 1

                for row in duplicates:
                    report.add_issue(
                        ValidationIssue(
                            code="DUPLICATE_FILENAME",
                            message=f"Duplicate filename found: {row['filename']} ({row['cnt']} occurrences)",
                            severity=ValidationSeverity.WARNING,
                            field="filename",
                            suggestion="Review and merge/remove duplicate entries",
                        )
                    )

            if "nulls" in checks:
                # 필수 필드 NULL 체크
                cursor = conn.execute(
                    """
                    SELECT id, filename
                    FROM video_files
                    WHERE filename IS NULL OR filename = ''
                    """
                )
                nulls = cursor.fetchall()
                report.checked_items += 1

                for row in nulls:
                    report.add_issue(
                        ValidationIssue(
                            code="NULL_REQUIRED_FIELD",
                            message=f"Record {row['id']} has null/empty filename",
                            severity=ValidationSeverity.ERROR,
                            field="filename",
                            record_id=str(row['id']),
                        )
                    )

            if "references" in checks:
                # 참조 무결성 체크 (project 존재 여부 등)
                # 여기서는 예시로 project 필드가 projects 테이블에 있는지 체크
                try:
                    cursor = conn.execute(
                        """
                        SELECT v.id, v.project
                        FROM video_files v
                        LEFT JOIN projects p ON v.project = p.name
                        WHERE v.project IS NOT NULL AND p.name IS NULL
                        LIMIT 100
                        """
                    )
                    orphan_refs = cursor.fetchall()
                    report.checked_items += 1

                    for row in orphan_refs:
                        report.add_issue(
                            ValidationIssue(
                                code="INVALID_REFERENCE",
                                message=f"Record {row['id']} references non-existent project: {row['project']}",
                                severity=ValidationSeverity.WARNING,
                                field="project",
                                record_id=str(row['id']),
                            )
                        )
                except sqlite3.OperationalError:
                    # projects 테이블이 없을 수 있음
                    pass

        self._track_tokens(report.checked_items * 50)

        return AgentResult.success_result(
            data=report.to_dict(),
            metrics={
                "checks_performed": len(checks),
                "issues_found": len(report.issues),
            },
        )

    async def _check_orphans(self, input_data: Dict[str, Any]) -> AgentResult:
        """고아 레코드 검색"""
        table = input_data.get("table", "video_files")
        path_column = input_data.get("path_column", "path")

        report = ValidationReport()

        if not self._file_check_enabled:
            return AgentResult.success_result(
                data=report.to_dict(),
                warnings=["File check is disabled"],
            )

        with self._get_connection() as conn:
            cursor = conn.execute(
                f"SELECT id, {path_column} as path FROM {table} WHERE {path_column} IS NOT NULL LIMIT 1000"
            )
            rows = cursor.fetchall()

            report.checked_items = len(rows)

            for row in rows:
                path = row["path"]
                if path and not Path(path).exists():
                    report.add_issue(
                        ValidationIssue(
                            code="ORPHAN_RECORD",
                            message=f"File no longer exists: {path}",
                            severity=ValidationSeverity.WARNING,
                            field=path_column,
                            record_id=str(row["id"]),
                            suggestion="Remove record or update path",
                        )
                    )

        self._track_tokens(report.checked_items * 5)

        return AgentResult.success_result(
            data=report.to_dict(),
            metrics={
                "records_checked": report.checked_items,
                "orphans_found": report.warnings,
            },
        )

    async def _generate_report(self, input_data: Dict[str, Any]) -> AgentResult:
        """종합 검증 리포트 생성"""
        include_checks = input_data.get(
            "checks",
            ["schema", "consistency", "files"]
        )

        combined_report = ValidationReport()

        # 스키마 검증
        if "schema" in include_checks:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM video_files LIMIT 100")
                records = [dict(row) for row in cursor.fetchall()]

            batch_result = await self._validate_batch({
                "schema": "video_files",
                "records": records,
            })
            if batch_result.data:
                for issue_data in batch_result.data.get("issues", []):
                    combined_report.add_issue(
                        ValidationIssue(
                            code=issue_data["code"],
                            message=issue_data["message"],
                            severity=ValidationSeverity(issue_data["severity"]),
                            field=issue_data.get("field"),
                            record_id=issue_data.get("record_id"),
                        )
                    )
                combined_report.checked_items += batch_result.data.get("checked_items", 0)

        # 일관성 검증
        if "consistency" in include_checks:
            consistency_result = await self._check_consistency({})
            if consistency_result.data:
                for issue_data in consistency_result.data.get("issues", []):
                    combined_report.add_issue(
                        ValidationIssue(
                            code=issue_data["code"],
                            message=issue_data["message"],
                            severity=ValidationSeverity(issue_data["severity"]),
                            field=issue_data.get("field"),
                            record_id=issue_data.get("record_id"),
                        )
                    )

        self._track_tokens(combined_report.checked_items * 10)

        return AgentResult.success_result(
            data={
                "report": combined_report.to_dict(),
                "summary": {
                    "passed": combined_report.passed,
                    "total_checks": combined_report.checked_items,
                    "total_errors": combined_report.errors,
                    "total_warnings": combined_report.warnings,
                },
            },
        )
