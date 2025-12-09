"""
Query Block Agent

고급 검색 및 쿼리 기능을 담당합니다.

Capabilities:
    - full_text_search: 전문 검색
    - faceted_search: 패싯 검색
    - build_query: 동적 쿼리 빌드
    - aggregate: 집계 연산
"""

from .query_agent import QueryAgent

__all__ = ["QueryAgent"]
