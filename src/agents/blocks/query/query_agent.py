"""
QueryAgent - 고급 검색 전담 에이전트

복잡한 검색 쿼리와 집계를 담당합니다.

주요 기능:
- 전문 검색 (Full-text search)
- 패싯 검색 (Faceted search)
- 동적 쿼리 빌더
- 집계 연산
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager

from ...core.base_agent import BaseAgent
from ...core.agent_context import AgentContext
from ...core.agent_result import AgentResult
from ...core.exceptions import AgentExecutionError


class SortOrder(Enum):
    """정렬 순서"""
    ASC = "ASC"
    DESC = "DESC"


@dataclass
class QueryFilter:
    """쿼리 필터"""

    field: str
    operator: str  # eq, ne, gt, gte, lt, lte, like, in, between
    value: Any
    logic: str = "AND"  # AND, OR

    def to_sql(self) -> Tuple[str, List[Any]]:
        """SQL 조건문으로 변환"""
        field_safe = "".join(c if c.isalnum() or c == "_" else "" for c in self.field)

        if self.operator == "eq":
            return f"{field_safe} = ?", [self.value]
        elif self.operator == "ne":
            return f"{field_safe} != ?", [self.value]
        elif self.operator == "gt":
            return f"{field_safe} > ?", [self.value]
        elif self.operator == "gte":
            return f"{field_safe} >= ?", [self.value]
        elif self.operator == "lt":
            return f"{field_safe} < ?", [self.value]
        elif self.operator == "lte":
            return f"{field_safe} <= ?", [self.value]
        elif self.operator == "like":
            return f"{field_safe} LIKE ?", [f"%{self.value}%"]
        elif self.operator == "in":
            placeholders = ", ".join("?" for _ in self.value)
            return f"{field_safe} IN ({placeholders})", list(self.value)
        elif self.operator == "between":
            return f"{field_safe} BETWEEN ? AND ?", list(self.value[:2])
        elif self.operator == "is_null":
            return f"{field_safe} IS NULL", []
        elif self.operator == "is_not_null":
            return f"{field_safe} IS NOT NULL", []
        else:
            raise ValueError(f"Unknown operator: {self.operator}")


@dataclass
class QueryBuilder:
    """동적 쿼리 빌더"""

    table: str
    columns: List[str] = field(default_factory=lambda: ["*"])
    filters: List[QueryFilter] = field(default_factory=list)
    order_by: List[Tuple[str, SortOrder]] = field(default_factory=list)
    group_by: List[str] = field(default_factory=list)
    having: List[QueryFilter] = field(default_factory=list)
    limit: Optional[int] = None
    offset: int = 0
    joins: List[str] = field(default_factory=list)

    def build(self) -> Tuple[str, List[Any]]:
        """SQL 쿼리 생성"""
        params = []
        table_safe = "".join(c if c.isalnum() or c == "_" else "" for c in self.table)

        # SELECT
        if self.columns == ["*"]:
            col_str = "*"
        else:
            col_str = ", ".join(self.columns)

        sql = f"SELECT {col_str} FROM {table_safe}"

        # JOINs
        for join in self.joins:
            sql += f" {join}"

        # WHERE
        if self.filters:
            conditions = []
            for i, f in enumerate(self.filters):
                condition, values = f.to_sql()
                if i > 0:
                    conditions.append(f"{f.logic} {condition}")
                else:
                    conditions.append(condition)
                params.extend(values)

            sql += f" WHERE {' '.join(conditions)}"

        # GROUP BY
        if self.group_by:
            group_cols = ", ".join(
                "".join(c if c.isalnum() or c == "_" else "" for c in col)
                for col in self.group_by
            )
            sql += f" GROUP BY {group_cols}"

        # HAVING
        if self.having:
            having_conditions = []
            for h in self.having:
                condition, values = h.to_sql()
                having_conditions.append(condition)
                params.extend(values)
            sql += f" HAVING {' AND '.join(having_conditions)}"

        # ORDER BY
        if self.order_by:
            order_parts = []
            for col, order in self.order_by:
                col_safe = "".join(c if c.isalnum() or c == "_" else "" for c in col)
                order_parts.append(f"{col_safe} {order.value}")
            sql += f" ORDER BY {', '.join(order_parts)}"

        # LIMIT/OFFSET
        if self.limit is not None:
            sql += f" LIMIT {int(self.limit)}"
        if self.offset > 0:
            sql += f" OFFSET {int(self.offset)}"

        return sql, params


@dataclass
class SearchResult:
    """검색 결과"""

    items: List[Dict[str, Any]] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    facets: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": (self.total + self.page_size - 1) // self.page_size if self.page_size > 0 else 0,
            "facets": self.facets,
        }


class QueryAgent(BaseAgent):
    """
    고급 검색 전담 에이전트

    복잡한 검색 쿼리와 집계를 수행합니다.

    사용법:
        agent = QueryAgent(config={"db_path": "pokervod.db"})
        result = await agent.execute(context, {
            "action": "search",
            "table": "video_files",
            "query": "WSOP 2023",
            "filters": [{"field": "project", "operator": "eq", "value": "WSOP"}],
            "facets": ["project", "year"]
        })

    Capabilities:
        - search: 검색 실행
        - full_text_search: 전문 검색
        - faceted_search: 패싯 검색
        - build_query: 동적 쿼리 빌드
        - aggregate: 집계 연산
        - count: 레코드 수 조회
    """

    # 검색 가능한 테이블
    SEARCHABLE_TABLES = {"video_files", "video_metadata", "projects", "events"}

    # FTS 컬럼 (전문 검색)
    FTS_COLUMNS = {
        "video_files": ["filename", "title", "description"],
        "video_metadata": ["event_name", "stage", "extra"],
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 에이전트 설정
                - db_path: 데이터베이스 경로
                - default_page_size: 기본 페이지 크기
                - max_page_size: 최대 페이지 크기
        """
        super().__init__("BLOCK_QUERY", config)

        self._db_path = self.config.get("db_path", "")
        self._default_page_size = self.config.get("default_page_size", 20)
        self._max_page_size = self.config.get("max_page_size", 100)

    def get_capabilities(self) -> List[str]:
        """에이전트 능력 목록"""
        return [
            "search",
            "full_text_search",
            "faceted_search",
            "build_query",
            "aggregate",
            "count",
        ]

    @contextmanager
    def _get_connection(self):
        """데이터베이스 연결"""
        if not self._db_path:
            raise AgentExecutionError("db_path is not configured", self.block_id)

        conn = sqlite3.connect(self._db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row

        try:
            yield conn
        finally:
            conn.close()

    def _validate_table(self, table: str) -> bool:
        """테이블 검증"""
        if table not in self.SEARCHABLE_TABLES:
            raise AgentExecutionError(
                f"Table not searchable: {table}. Allowed: {self.SEARCHABLE_TABLES}",
                self.block_id,
            )
        return True

    async def execute(
        self, context: AgentContext, input_data: Dict[str, Any]
    ) -> AgentResult:
        """
        메인 실행 로직

        Args:
            context: 실행 컨텍스트
            input_data: 입력 데이터

        Returns:
            AgentResult: 검색 결과
        """
        try:
            await self.pre_execute(context)

            action = input_data.get("action", "search")

            if action == "search":
                result = await self._search(input_data)
            elif action == "full_text_search":
                result = await self._full_text_search(input_data)
            elif action == "faceted_search":
                result = await self._faceted_search(input_data)
            elif action == "build_query":
                result = await self._build_query(input_data)
            elif action == "aggregate":
                result = await self._aggregate(input_data)
            elif action == "count":
                result = await self._count(input_data)
            else:
                raise AgentExecutionError(
                    f"Unknown action: {action}", self.block_id
                )

            await self.post_execute(result)
            return result

        except Exception as e:
            return await self.handle_error(e, context)

    async def _search(self, input_data: Dict[str, Any]) -> AgentResult:
        """기본 검색"""
        table = input_data.get("table", "video_files")
        filters_data = input_data.get("filters", [])
        columns = input_data.get("columns", ["*"])
        order_by = input_data.get("order_by", [])
        page = input_data.get("page", 1)
        page_size = min(
            input_data.get("page_size", self._default_page_size),
            self._max_page_size,
        )

        self._validate_table(table)

        # 필터 변환
        filters = [
            QueryFilter(
                field=f["field"],
                operator=f.get("operator", "eq"),
                value=f["value"],
                logic=f.get("logic", "AND"),
            )
            for f in filters_data
        ]

        # 정렬 변환
        order = [
            (o["field"], SortOrder(o.get("order", "ASC").upper()))
            for o in order_by
        ] if order_by else []

        # 쿼리 빌드
        builder = QueryBuilder(
            table=table,
            columns=columns,
            filters=filters,
            order_by=order,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

        sql, params = builder.build()
        self._track_tokens(self._estimate_tokens(sql))

        # 실행
        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            items = [dict(row) for row in cursor.fetchall()]

            # 총 개수
            count_sql = f"SELECT COUNT(*) as cnt FROM {table}"
            if filters:
                where_parts = []
                count_params = []
                for f in filters:
                    cond, vals = f.to_sql()
                    where_parts.append(cond)
                    count_params.extend(vals)
                count_sql += f" WHERE {' AND '.join(where_parts)}"
            else:
                count_params = []

            count_cursor = conn.execute(count_sql, count_params)
            total = count_cursor.fetchone()["cnt"]

        result = SearchResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

        return AgentResult.success_result(
            data=result.to_dict(),
            metrics={"items_returned": len(items), "total": total},
        )

    async def _full_text_search(self, input_data: Dict[str, Any]) -> AgentResult:
        """전문 검색"""
        table = input_data.get("table", "video_files")
        query = input_data.get("query", "")
        page = input_data.get("page", 1)
        page_size = min(
            input_data.get("page_size", self._default_page_size),
            self._max_page_size,
        )

        if not query:
            return AgentResult.failure_result(
                errors=["query is required for full text search"],
                error_type="ValidationError",
            )

        self._validate_table(table)

        # FTS 컬럼 확인
        fts_columns = self.FTS_COLUMNS.get(table, ["filename"])

        # LIKE 기반 검색 (SQLite FTS 미설정 시)
        conditions = []
        params = []
        for col in fts_columns:
            conditions.append(f"{col} LIKE ?")
            params.append(f"%{query}%")

        where_clause = " OR ".join(conditions)
        sql = f"SELECT * FROM {table} WHERE {where_clause} LIMIT ? OFFSET ?"
        params.extend([page_size, (page - 1) * page_size])

        self._track_tokens(self._estimate_tokens(sql))

        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            items = [dict(row) for row in cursor.fetchall()]

            # 총 개수
            count_sql = f"SELECT COUNT(*) as cnt FROM {table} WHERE {where_clause}"
            count_cursor = conn.execute(count_sql, params[:-2])
            total = count_cursor.fetchone()["cnt"]

        result = SearchResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

        return AgentResult.success_result(
            data=result.to_dict(),
            metrics={"items_returned": len(items), "total": total, "query": query},
        )

    async def _faceted_search(self, input_data: Dict[str, Any]) -> AgentResult:
        """패싯 검색"""
        table = input_data.get("table", "video_files")
        facet_fields = input_data.get("facets", [])
        filters_data = input_data.get("filters", [])
        page = input_data.get("page", 1)
        page_size = min(
            input_data.get("page_size", self._default_page_size),
            self._max_page_size,
        )

        self._validate_table(table)

        # 필터 변환
        filters = [
            QueryFilter(
                field=f["field"],
                operator=f.get("operator", "eq"),
                value=f["value"],
            )
            for f in filters_data
        ]

        # 기본 검색
        builder = QueryBuilder(
            table=table,
            filters=filters,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

        sql, params = builder.build()
        self._track_tokens(self._estimate_tokens(sql))

        facets = {}

        with self._get_connection() as conn:
            # 메인 결과
            cursor = conn.execute(sql, params)
            items = [dict(row) for row in cursor.fetchall()]

            # 총 개수
            count_sql = f"SELECT COUNT(*) as cnt FROM {table}"
            if filters:
                where_parts = []
                count_params = []
                for f in filters:
                    cond, vals = f.to_sql()
                    where_parts.append(cond)
                    count_params.extend(vals)
                count_sql += f" WHERE {' AND '.join(where_parts)}"
            else:
                count_params = []

            count_cursor = conn.execute(count_sql, count_params)
            total = count_cursor.fetchone()["cnt"]

            # 패싯 집계
            for facet_field in facet_fields:
                facet_safe = "".join(
                    c if c.isalnum() or c == "_" else "" for c in facet_field
                )
                facet_sql = (
                    f"SELECT {facet_safe} as value, COUNT(*) as count "
                    f"FROM {table} GROUP BY {facet_safe} ORDER BY count DESC LIMIT 20"
                )
                facet_cursor = conn.execute(facet_sql)
                facets[facet_field] = [
                    {"value": row["value"], "count": row["count"]}
                    for row in facet_cursor.fetchall()
                    if row["value"] is not None
                ]

        result = SearchResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            facets=facets,
        )

        return AgentResult.success_result(
            data=result.to_dict(),
            metrics={"items_returned": len(items), "facet_count": len(facets)},
        )

    async def _build_query(self, input_data: Dict[str, Any]) -> AgentResult:
        """쿼리 빌드 (SQL 반환)"""
        table = input_data.get("table", "")
        columns = input_data.get("columns", ["*"])
        filters_data = input_data.get("filters", [])
        order_by = input_data.get("order_by", [])
        group_by = input_data.get("group_by", [])
        limit = input_data.get("limit")

        if not table:
            return AgentResult.failure_result(
                errors=["table is required"],
                error_type="ValidationError",
            )

        filters = [
            QueryFilter(
                field=f["field"],
                operator=f.get("operator", "eq"),
                value=f["value"],
            )
            for f in filters_data
        ]

        order = [
            (o["field"], SortOrder(o.get("order", "ASC").upper()))
            for o in order_by
        ] if order_by else []

        builder = QueryBuilder(
            table=table,
            columns=columns,
            filters=filters,
            order_by=order,
            group_by=group_by,
            limit=limit,
        )

        sql, params = builder.build()

        return AgentResult.success_result(
            data={"sql": sql, "params": params},
        )

    async def _aggregate(self, input_data: Dict[str, Any]) -> AgentResult:
        """집계 연산"""
        table = input_data.get("table", "")
        aggregations = input_data.get("aggregations", [])
        group_by = input_data.get("group_by", [])
        filters_data = input_data.get("filters", [])

        if not table or not aggregations:
            return AgentResult.failure_result(
                errors=["table and aggregations are required"],
                error_type="ValidationError",
            )

        self._validate_table(table)

        # 집계 함수 생성
        agg_parts = []
        for agg in aggregations:
            func = agg.get("function", "COUNT").upper()
            field = agg.get("field", "*")
            alias = agg.get("alias", f"{func.lower()}_{field}")

            field_safe = "*" if field == "*" else "".join(
                c if c.isalnum() or c == "_" else "" for c in field
            )
            alias_safe = "".join(c if c.isalnum() or c == "_" else "" for c in alias)

            agg_parts.append(f"{func}({field_safe}) as {alias_safe}")

        # GROUP BY
        if group_by:
            group_safe = [
                "".join(c if c.isalnum() or c == "_" else "" for c in col)
                for col in group_by
            ]
            select_cols = group_safe + agg_parts
            sql = f"SELECT {', '.join(select_cols)} FROM {table}"
        else:
            sql = f"SELECT {', '.join(agg_parts)} FROM {table}"

        # WHERE
        params = []
        if filters_data:
            filters = [
                QueryFilter(
                    field=f["field"],
                    operator=f.get("operator", "eq"),
                    value=f["value"],
                )
                for f in filters_data
            ]
            where_parts = []
            for f in filters:
                cond, vals = f.to_sql()
                where_parts.append(cond)
                params.extend(vals)
            sql += f" WHERE {' AND '.join(where_parts)}"

        # GROUP BY
        if group_by:
            sql += f" GROUP BY {', '.join(group_safe)}"

        self._track_tokens(self._estimate_tokens(sql))

        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]

        return AgentResult.success_result(
            data={"results": rows, "sql": sql},
            metrics={"rows_returned": len(rows)},
        )

    async def _count(self, input_data: Dict[str, Any]) -> AgentResult:
        """레코드 수 조회"""
        table = input_data.get("table", "")
        filters_data = input_data.get("filters", [])

        if not table:
            return AgentResult.failure_result(
                errors=["table is required"],
                error_type="ValidationError",
            )

        self._validate_table(table)

        sql = f"SELECT COUNT(*) as count FROM {table}"
        params = []

        if filters_data:
            filters = [
                QueryFilter(
                    field=f["field"],
                    operator=f.get("operator", "eq"),
                    value=f["value"],
                )
                for f in filters_data
            ]
            where_parts = []
            for f in filters:
                cond, vals = f.to_sql()
                where_parts.append(cond)
                params.extend(vals)
            sql += f" WHERE {' AND '.join(where_parts)}"

        self._track_tokens(self._estimate_tokens(sql))

        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            count = cursor.fetchone()["count"]

        return AgentResult.success_result(
            data={"count": count},
        )
