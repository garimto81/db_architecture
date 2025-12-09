"""
StorageAgent - SQLite 저장소 전담 에이전트

SQLite 데이터베이스에 대한 CRUD 작업을 담당합니다.

주요 기능:
- 레코드 저장/업데이트/삭제
- 벌크 upsert
- 트랜잭션 관리
- 스키마 검증
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
from contextlib import contextmanager
import json

from ...core.base_agent import BaseAgent
from ...core.agent_context import AgentContext
from ...core.agent_result import AgentResult
from ...core.exceptions import AgentExecutionError


@dataclass
class QueryResult:
    """쿼리 결과"""

    rows: List[Dict[str, Any]] = field(default_factory=list)
    affected_rows: int = 0
    last_insert_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rows": self.rows,
            "affected_rows": self.affected_rows,
            "last_insert_id": self.last_insert_id,
        }


class StorageAgent(BaseAgent):
    """
    SQLite 저장소 전담 에이전트

    데이터베이스 CRUD 작업을 안전하게 수행합니다.

    사용법:
        agent = StorageAgent(config={"db_path": "pokervod.db"})
        result = await agent.execute(context, {
            "action": "save_record",
            "table": "video_files",
            "data": {"filename": "test.mp4", "project": "WSOP"}
        })

    Capabilities:
        - save_record: 단일 레코드 저장
        - update_record: 레코드 업데이트
        - delete_record: 레코드 삭제
        - query_records: 레코드 조회
        - bulk_upsert: 대량 upsert
        - execute_sql: 직접 SQL 실행 (읽기 전용)
    """

    # 보호된 테이블 (스키마 변경 금지)
    PROTECTED_TABLES = {"sqlite_master", "sqlite_sequence"}

    # 허용된 테이블
    ALLOWED_TABLES = {
        "video_files",
        "video_metadata",
        "sync_history",
        "projects",
        "events",
        "validation_logs",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 에이전트 설정
                - db_path: 데이터베이스 파일 경로
                - readonly: 읽기 전용 모드 (기본: False)
                - timeout: 연결 타임아웃 (기본: 30)
        """
        super().__init__("BLOCK_STORAGE", config)

        self._db_path = self.config.get("db_path", "")
        self._readonly = self.config.get("readonly", False)
        self._timeout = self.config.get("timeout", 30)
        self._connection: Optional[sqlite3.Connection] = None

    def get_capabilities(self) -> List[str]:
        """에이전트 능력 목록"""
        return [
            "save_record",
            "update_record",
            "delete_record",
            "query_records",
            "bulk_upsert",
            "execute_sql",
            "get_schema",
        ]

    @contextmanager
    def _get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        if not self._db_path:
            raise AgentExecutionError("db_path is not configured", self.block_id)

        conn = sqlite3.connect(
            self._db_path,
            timeout=self._timeout,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = sqlite3.Row

        try:
            yield conn
            if not self._readonly:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _validate_table(self, table: str) -> bool:
        """테이블 이름 검증"""
        if table in self.PROTECTED_TABLES:
            raise AgentExecutionError(
                f"Cannot access protected table: {table}", self.block_id
            )
        if table not in self.ALLOWED_TABLES:
            self.logger.warning(f"Accessing non-standard table: {table}")
        return True

    def _sanitize_identifier(self, name: str) -> str:
        """SQL 식별자 sanitize"""
        # 알파벳, 숫자, 언더스코어만 허용
        sanitized = "".join(c if c.isalnum() or c == "_" else "" for c in name)
        return sanitized

    async def execute(
        self, context: AgentContext, input_data: Dict[str, Any]
    ) -> AgentResult:
        """
        메인 실행 로직

        Args:
            context: 실행 컨텍스트
            input_data: 입력 데이터
                - action: 수행할 액션
                - table: 테이블명
                - data: 데이터 (딕셔너리 또는 리스트)
                - where: WHERE 조건

        Returns:
            AgentResult: 실행 결과
        """
        try:
            await self.pre_execute(context)

            action = input_data.get("action", "query_records")

            if action == "save_record":
                result = await self._save_record(input_data)
            elif action == "update_record":
                result = await self._update_record(input_data)
            elif action == "delete_record":
                result = await self._delete_record(input_data)
            elif action == "query_records":
                result = await self._query_records(input_data)
            elif action == "bulk_upsert":
                result = await self._bulk_upsert(input_data)
            elif action == "execute_sql":
                result = await self._execute_sql(input_data)
            elif action == "get_schema":
                result = await self._get_schema(input_data)
            else:
                raise AgentExecutionError(
                    f"Unknown action: {action}", self.block_id
                )

            await self.post_execute(result)
            return result

        except Exception as e:
            return await self.handle_error(e, context)

    async def _save_record(self, input_data: Dict[str, Any]) -> AgentResult:
        """단일 레코드 저장"""
        table = input_data.get("table", "")
        data = input_data.get("data", {})

        if not table or not data:
            return AgentResult.failure_result(
                errors=["table and data are required"],
                error_type="ValidationError",
            )

        self._validate_table(table)
        table = self._sanitize_identifier(table)

        columns = [self._sanitize_identifier(k) for k in data.keys()]
        placeholders = ["?" for _ in columns]
        values = list(data.values())

        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"

        self._track_tokens(self._estimate_tokens(sql))

        with self._get_connection() as conn:
            cursor = conn.execute(sql, values)
            result = QueryResult(
                affected_rows=cursor.rowcount,
                last_insert_id=cursor.lastrowid,
            )

        self.logger.info(f"Saved record to {table}, id={result.last_insert_id}")

        return AgentResult.success_result(
            data=result.to_dict(),
            metrics={"rows_affected": result.affected_rows},
        )

    async def _update_record(self, input_data: Dict[str, Any]) -> AgentResult:
        """레코드 업데이트"""
        table = input_data.get("table", "")
        data = input_data.get("data", {})
        where = input_data.get("where", {})

        if not table or not data:
            return AgentResult.failure_result(
                errors=["table and data are required"],
                error_type="ValidationError",
            )

        if not where:
            return AgentResult.failure_result(
                errors=["where clause is required for update"],
                error_type="ValidationError",
            )

        self._validate_table(table)
        table = self._sanitize_identifier(table)

        set_parts = [f"{self._sanitize_identifier(k)} = ?" for k in data.keys()]
        where_parts = [f"{self._sanitize_identifier(k)} = ?" for k in where.keys()]

        sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {' AND '.join(where_parts)}"
        values = list(data.values()) + list(where.values())

        self._track_tokens(self._estimate_tokens(sql))

        with self._get_connection() as conn:
            cursor = conn.execute(sql, values)
            result = QueryResult(affected_rows=cursor.rowcount)

        self.logger.info(f"Updated {result.affected_rows} records in {table}")

        return AgentResult.success_result(
            data=result.to_dict(),
            metrics={"rows_affected": result.affected_rows},
        )

    async def _delete_record(self, input_data: Dict[str, Any]) -> AgentResult:
        """레코드 삭제"""
        table = input_data.get("table", "")
        where = input_data.get("where", {})

        if not table:
            return AgentResult.failure_result(
                errors=["table is required"],
                error_type="ValidationError",
            )

        if not where:
            return AgentResult.failure_result(
                errors=["where clause is required for delete"],
                error_type="ValidationError",
            )

        self._validate_table(table)
        table = self._sanitize_identifier(table)

        where_parts = [f"{self._sanitize_identifier(k)} = ?" for k in where.keys()]
        sql = f"DELETE FROM {table} WHERE {' AND '.join(where_parts)}"
        values = list(where.values())

        self._track_tokens(self._estimate_tokens(sql))

        with self._get_connection() as conn:
            cursor = conn.execute(sql, values)
            result = QueryResult(affected_rows=cursor.rowcount)

        self.logger.info(f"Deleted {result.affected_rows} records from {table}")

        return AgentResult.success_result(
            data=result.to_dict(),
            metrics={"rows_affected": result.affected_rows},
        )

    async def _query_records(self, input_data: Dict[str, Any]) -> AgentResult:
        """레코드 조회"""
        table = input_data.get("table", "")
        columns = input_data.get("columns", ["*"])
        where = input_data.get("where", {})
        order_by = input_data.get("order_by", "")
        limit = input_data.get("limit", 100)
        offset = input_data.get("offset", 0)

        if not table:
            return AgentResult.failure_result(
                errors=["table is required"],
                error_type="ValidationError",
            )

        self._validate_table(table)
        table = self._sanitize_identifier(table)

        if columns == ["*"]:
            col_str = "*"
        else:
            col_str = ", ".join(self._sanitize_identifier(c) for c in columns)

        sql = f"SELECT {col_str} FROM {table}"
        values = []

        if where:
            where_parts = [f"{self._sanitize_identifier(k)} = ?" for k in where.keys()]
            sql += f" WHERE {' AND '.join(where_parts)}"
            values = list(where.values())

        if order_by:
            sql += f" ORDER BY {self._sanitize_identifier(order_by)}"

        sql += f" LIMIT {int(limit)} OFFSET {int(offset)}"

        self._track_tokens(self._estimate_tokens(sql))

        with self._get_connection() as conn:
            cursor = conn.execute(sql, values)
            rows = [dict(row) for row in cursor.fetchall()]
            result = QueryResult(rows=rows, affected_rows=len(rows))

        return AgentResult.success_result(
            data=result.to_dict(),
            metrics={"rows_returned": len(rows)},
        )

    async def _bulk_upsert(self, input_data: Dict[str, Any]) -> AgentResult:
        """대량 upsert"""
        table = input_data.get("table", "")
        records = input_data.get("records", [])
        conflict_columns = input_data.get("conflict_columns", [])

        if not table or not records:
            return AgentResult.failure_result(
                errors=["table and records are required"],
                error_type="ValidationError",
            )

        self._validate_table(table)
        table = self._sanitize_identifier(table)

        if not records:
            return AgentResult.success_result(
                data={"inserted": 0, "updated": 0},
            )

        # 첫 번째 레코드에서 컬럼 추출
        columns = [self._sanitize_identifier(k) for k in records[0].keys()]
        placeholders = ["?" for _ in columns]

        # UPSERT SQL 생성 (SQLite 3.24+)
        if conflict_columns:
            conflict_cols = ", ".join(self._sanitize_identifier(c) for c in conflict_columns)
            update_cols = ", ".join(
                f"{c} = excluded.{c}" for c in columns if c not in conflict_columns
            )
            sql = (
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join(placeholders)}) "
                f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_cols}"
            )
        else:
            sql = (
                f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join(placeholders)})"
            )

        self._track_tokens(self._estimate_tokens(sql) * len(records) // 10)

        total_affected = 0
        with self._get_connection() as conn:
            for record in records:
                values = [record.get(k) for k in records[0].keys()]
                cursor = conn.execute(sql, values)
                total_affected += cursor.rowcount

        self.logger.info(f"Bulk upserted {total_affected} records to {table}")

        return AgentResult.success_result(
            data={"affected_rows": total_affected, "total_records": len(records)},
            metrics={"rows_affected": total_affected},
        )

    async def _execute_sql(self, input_data: Dict[str, Any]) -> AgentResult:
        """직접 SQL 실행 (읽기 전용)"""
        sql = input_data.get("sql", "")
        params = input_data.get("params", [])

        if not sql:
            return AgentResult.failure_result(
                errors=["sql is required"],
                error_type="ValidationError",
            )

        # 읽기 전용 검증
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            return AgentResult.failure_result(
                errors=["Only SELECT statements are allowed in execute_sql"],
                error_type="PermissionError",
            )

        self._track_tokens(self._estimate_tokens(sql))

        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
            result = QueryResult(rows=rows, affected_rows=len(rows))

        return AgentResult.success_result(
            data=result.to_dict(),
            metrics={"rows_returned": len(rows)},
        )

    async def _get_schema(self, input_data: Dict[str, Any]) -> AgentResult:
        """테이블 스키마 조회"""
        table = input_data.get("table", "")

        if not table:
            # 모든 테이블 목록 반환
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = [row["name"] for row in cursor.fetchall()]

            return AgentResult.success_result(
                data={"tables": tables},
            )

        self._validate_table(table)
        table = self._sanitize_identifier(table)

        with self._get_connection() as conn:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "nullable": not row["notnull"],
                    "default": row["dflt_value"],
                    "primary_key": bool(row["pk"]),
                }
                for row in cursor.fetchall()
            ]

        return AgentResult.success_result(
            data={"table": table, "columns": columns},
        )
