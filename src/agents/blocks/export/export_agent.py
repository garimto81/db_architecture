"""
ExportAgent - 데이터 내보내기 전담 에이전트

다양한 형식으로 데이터를 내보냅니다.

주요 기능:
- CSV 내보내기
- JSON 내보내기
- Google Sheets 내보내기 (시뮬레이션)
- 리포트 생성
"""

import csv
import json
import io
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import sqlite3
from contextlib import contextmanager

from ...core.base_agent import BaseAgent
from ...core.agent_context import AgentContext
from ...core.agent_result import AgentResult
from ...core.exceptions import AgentExecutionError


@dataclass
class ExportConfig:
    """내보내기 설정"""

    format: str = "csv"  # csv, json, jsonl, sheets
    columns: List[str] = field(default_factory=list)  # 빈 리스트 = 모든 컬럼
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: Optional[int] = None
    include_header: bool = True
    pretty_json: bool = True
    encoding: str = "utf-8"


@dataclass
class ExportResult:
    """내보내기 결과"""

    format: str
    records_exported: int
    file_path: Optional[str] = None
    content: Optional[str] = None
    size_bytes: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": self.format,
            "records_exported": self.records_exported,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes,
            "timestamp": self.timestamp.isoformat(),
        }


class ExportAgent(BaseAgent):
    """
    데이터 내보내기 전담 에이전트

    다양한 형식으로 데이터를 내보냅니다.

    사용법:
        agent = ExportAgent(config={"db_path": "pokervod.db"})
        result = await agent.execute(context, {
            "action": "export_csv",
            "table": "video_files",
            "output_path": "export/videos.csv",
            "columns": ["filename", "project", "year"]
        })

    Capabilities:
        - export_csv: CSV 형식 내보내기
        - export_json: JSON 형식 내보내기
        - export_jsonl: JSON Lines 형식 내보내기
        - export_sheets: Google Sheets 내보내기 (시뮬레이션)
        - generate_report: 통계 리포트 생성
        - export_to_string: 문자열로 내보내기 (파일 저장 없음)
    """

    # 지원 포맷
    SUPPORTED_FORMATS = {"csv", "json", "jsonl", "sheets"}

    # 내보내기 가능 테이블
    EXPORTABLE_TABLES = {"video_files", "video_metadata", "projects", "events", "sync_history"}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 에이전트 설정
                - db_path: 데이터베이스 경로
                - output_dir: 기본 출력 디렉토리
                - max_records: 최대 내보내기 레코드 수
        """
        super().__init__("BLOCK_EXPORT", config)

        self._db_path = self.config.get("db_path", "")
        self._output_dir = Path(self.config.get("output_dir", "exports"))
        self._max_records = self.config.get("max_records", 100000)

    def get_capabilities(self) -> List[str]:
        """에이전트 능력 목록"""
        return [
            "export_csv",
            "export_json",
            "export_jsonl",
            "export_sheets",
            "generate_report",
            "export_to_string",
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

    def _validate_table(self, table: str) -> bool:
        """테이블 검증"""
        if table not in self.EXPORTABLE_TABLES:
            raise AgentExecutionError(
                f"Table not exportable: {table}. Allowed: {self.EXPORTABLE_TABLES}",
                self.block_id,
            )
        return True

    def _sanitize_identifier(self, name: str) -> str:
        """SQL 식별자 sanitize"""
        return "".join(c if c.isalnum() or c == "_" else "" for c in name)

    def _ensure_output_dir(self) -> None:
        """출력 디렉토리 생성"""
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def execute(
        self, context: AgentContext, input_data: Dict[str, Any]
    ) -> AgentResult:
        """
        메인 실행 로직

        Args:
            context: 실행 컨텍스트
            input_data: 입력 데이터

        Returns:
            AgentResult: 내보내기 결과
        """
        try:
            await self.pre_execute(context)

            action = input_data.get("action", "export_csv")

            if action == "export_csv":
                result = await self._export_csv(input_data)
            elif action == "export_json":
                result = await self._export_json(input_data)
            elif action == "export_jsonl":
                result = await self._export_jsonl(input_data)
            elif action == "export_sheets":
                result = await self._export_sheets(input_data)
            elif action == "generate_report":
                result = await self._generate_report(input_data)
            elif action == "export_to_string":
                result = await self._export_to_string(input_data)
            else:
                raise AgentExecutionError(
                    f"Unknown action: {action}", self.block_id
                )

            await self.post_execute(result)
            return result

        except Exception as e:
            return await self.handle_error(e, context)

    def _fetch_data(
        self,
        table: str,
        columns: List[str],
        filters: Dict[str, Any],
        limit: Optional[int],
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """데이터 조회"""
        self._validate_table(table)
        table = self._sanitize_identifier(table)

        # 컬럼 처리
        if columns:
            col_str = ", ".join(self._sanitize_identifier(c) for c in columns)
        else:
            col_str = "*"

        sql = f"SELECT {col_str} FROM {table}"
        params = []

        # 필터 처리
        if filters:
            where_parts = []
            for field, value in filters.items():
                field_safe = self._sanitize_identifier(field)
                where_parts.append(f"{field_safe} = ?")
                params.append(value)
            sql += f" WHERE {' AND '.join(where_parts)}"

        # 제한
        effective_limit = min(limit or self._max_records, self._max_records)
        sql += f" LIMIT {effective_limit}"

        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            # 컬럼 이름
            if rows:
                column_names = list(rows[0].keys())
            else:
                column_names = columns if columns else []

            data = [dict(row) for row in rows]

        return column_names, data

    async def _export_csv(self, input_data: Dict[str, Any]) -> AgentResult:
        """CSV 형식 내보내기"""
        table = input_data.get("table", "video_files")
        columns = input_data.get("columns", [])
        filters = input_data.get("filters", {})
        limit = input_data.get("limit")
        output_path = input_data.get("output_path")
        include_header = input_data.get("include_header", True)

        column_names, data = self._fetch_data(table, columns, filters, limit)

        self._track_tokens(len(data) * 20)

        # CSV 생성
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=column_names)

        if include_header:
            writer.writeheader()

        for row in data:
            writer.writerow(row)

        csv_content = output.getvalue()

        # 파일 저장
        if output_path:
            self._ensure_output_dir()
            file_path = self._output_dir / output_path
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8", newline="") as f:
                f.write(csv_content)

            export_result = ExportResult(
                format="csv",
                records_exported=len(data),
                file_path=str(file_path),
                size_bytes=len(csv_content.encode("utf-8")),
            )
        else:
            export_result = ExportResult(
                format="csv",
                records_exported=len(data),
                content=csv_content,
                size_bytes=len(csv_content.encode("utf-8")),
            )

        return AgentResult.success_result(
            data=export_result.to_dict(),
            metrics={"records_exported": len(data)},
        )

    async def _export_json(self, input_data: Dict[str, Any]) -> AgentResult:
        """JSON 형식 내보내기"""
        table = input_data.get("table", "video_files")
        columns = input_data.get("columns", [])
        filters = input_data.get("filters", {})
        limit = input_data.get("limit")
        output_path = input_data.get("output_path")
        pretty = input_data.get("pretty", True)

        column_names, data = self._fetch_data(table, columns, filters, limit)

        self._track_tokens(len(data) * 30)

        # JSON 생성
        if pretty:
            json_content = json.dumps(
                {"data": data, "meta": {"table": table, "count": len(data)}},
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        else:
            json_content = json.dumps(
                {"data": data, "meta": {"table": table, "count": len(data)}},
                ensure_ascii=False,
                default=str,
            )

        # 파일 저장
        if output_path:
            self._ensure_output_dir()
            file_path = self._output_dir / output_path
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(json_content)

            export_result = ExportResult(
                format="json",
                records_exported=len(data),
                file_path=str(file_path),
                size_bytes=len(json_content.encode("utf-8")),
            )
        else:
            export_result = ExportResult(
                format="json",
                records_exported=len(data),
                content=json_content,
                size_bytes=len(json_content.encode("utf-8")),
            )

        return AgentResult.success_result(
            data=export_result.to_dict(),
            metrics={"records_exported": len(data)},
        )

    async def _export_jsonl(self, input_data: Dict[str, Any]) -> AgentResult:
        """JSON Lines 형식 내보내기"""
        table = input_data.get("table", "video_files")
        columns = input_data.get("columns", [])
        filters = input_data.get("filters", {})
        limit = input_data.get("limit")
        output_path = input_data.get("output_path")

        column_names, data = self._fetch_data(table, columns, filters, limit)

        self._track_tokens(len(data) * 25)

        # JSONL 생성
        lines = [
            json.dumps(row, ensure_ascii=False, default=str)
            for row in data
        ]
        jsonl_content = "\n".join(lines)

        # 파일 저장
        if output_path:
            self._ensure_output_dir()
            file_path = self._output_dir / output_path
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(jsonl_content)

            export_result = ExportResult(
                format="jsonl",
                records_exported=len(data),
                file_path=str(file_path),
                size_bytes=len(jsonl_content.encode("utf-8")),
            )
        else:
            export_result = ExportResult(
                format="jsonl",
                records_exported=len(data),
                content=jsonl_content,
                size_bytes=len(jsonl_content.encode("utf-8")),
            )

        return AgentResult.success_result(
            data=export_result.to_dict(),
            metrics={"records_exported": len(data)},
        )

    async def _export_sheets(self, input_data: Dict[str, Any]) -> AgentResult:
        """Google Sheets 내보내기 (시뮬레이션)"""
        table = input_data.get("table", "video_files")
        columns = input_data.get("columns", [])
        filters = input_data.get("filters", {})
        limit = input_data.get("limit")
        spreadsheet_id = input_data.get("spreadsheet_id", "")
        sheet_name = input_data.get("sheet_name", "Export")

        if not spreadsheet_id:
            return AgentResult.failure_result(
                errors=["spreadsheet_id is required for Sheets export"],
                error_type="ValidationError",
            )

        column_names, data = self._fetch_data(table, columns, filters, limit)

        self._track_tokens(len(data) * 20)

        # 실제 구현 시 google-auth, gspread 등 사용
        # 여기서는 시뮬레이션
        # from gspread import authorize, Client
        # gc = authorize(credentials)
        # sh = gc.open_by_key(spreadsheet_id)
        # worksheet = sh.worksheet(sheet_name)
        # worksheet.update([column_names] + [list(row.values()) for row in data])

        return AgentResult.success_result(
            data={
                "format": "sheets",
                "records_exported": len(data),
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": sheet_name,
            },
            warnings=["Google Sheets export is simulated - integrate gspread for production"],
            metrics={"records_exported": len(data)},
        )

    async def _generate_report(self, input_data: Dict[str, Any]) -> AgentResult:
        """통계 리포트 생성"""
        table = input_data.get("table", "video_files")
        output_format = input_data.get("format", "json")

        self._validate_table(table)
        table_safe = self._sanitize_identifier(table)

        report_data = {
            "table": table,
            "generated_at": datetime.utcnow().isoformat(),
            "statistics": {},
        }

        with self._get_connection() as conn:
            # 총 레코드 수
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table_safe}")
            report_data["statistics"]["total_records"] = cursor.fetchone()["count"]

            # 프로젝트별 통계 (해당 테이블에 project 컬럼이 있다면)
            try:
                cursor = conn.execute(
                    f"""
                    SELECT project, COUNT(*) as count
                    FROM {table_safe}
                    WHERE project IS NOT NULL
                    GROUP BY project
                    ORDER BY count DESC
                    LIMIT 10
                    """
                )
                report_data["statistics"]["by_project"] = [
                    {"project": row["project"], "count": row["count"]}
                    for row in cursor.fetchall()
                ]
            except sqlite3.OperationalError:
                pass

            # 연도별 통계
            try:
                cursor = conn.execute(
                    f"""
                    SELECT year, COUNT(*) as count
                    FROM {table_safe}
                    WHERE year IS NOT NULL
                    GROUP BY year
                    ORDER BY year DESC
                    LIMIT 10
                    """
                )
                report_data["statistics"]["by_year"] = [
                    {"year": row["year"], "count": row["count"]}
                    for row in cursor.fetchall()
                ]
            except sqlite3.OperationalError:
                pass

        self._track_tokens(100)

        return AgentResult.success_result(
            data=report_data,
            metrics={"total_records": report_data["statistics"].get("total_records", 0)},
        )

    async def _export_to_string(self, input_data: Dict[str, Any]) -> AgentResult:
        """문자열로 내보내기 (파일 저장 없음)"""
        export_format = input_data.get("format", "csv")

        # output_path 제거하여 문자열 반환 강제
        input_data_copy = {k: v for k, v in input_data.items() if k != "output_path"}

        if export_format == "csv":
            return await self._export_csv(input_data_copy)
        elif export_format == "json":
            return await self._export_json(input_data_copy)
        elif export_format == "jsonl":
            return await self._export_jsonl(input_data_copy)
        else:
            return AgentResult.failure_result(
                errors=[f"Unsupported format: {export_format}"],
                error_type="ValidationError",
            )


# 타입 힌트를 위한 Tuple import 추가
from typing import Tuple
