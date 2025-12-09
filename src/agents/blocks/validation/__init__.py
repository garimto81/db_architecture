"""
Validation Block Agent

데이터 무결성 검증을 담당합니다.

Capabilities:
    - validate_record: 레코드 검증
    - validate_file: 파일 검증
    - check_consistency: 일관성 체크
    - generate_report: 검증 리포트 생성
"""

from .validation_agent import ValidationAgent

__all__ = ["ValidationAgent"]
