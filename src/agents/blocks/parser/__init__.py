"""
Parser Block Agent

파일명 파싱 및 메타데이터 추출을 담당합니다.

Capabilities:
    - parse_filename: 파일명 파싱
    - detect_project: 프로젝트(대회) 감지
    - extract_metadata: 메타데이터 추출
"""

from .parser_agent import ParserAgent

__all__ = ["ParserAgent"]
