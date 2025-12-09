"""
Storage Block Agent

SQLite 데이터베이스 CRUD 작업을 담당합니다.

Capabilities:
    - save_record: 레코드 저장
    - update_record: 레코드 업데이트
    - query_records: 레코드 조회
    - delete_record: 레코드 삭제
    - bulk_upsert: 대량 upsert
"""

from .storage_agent import StorageAgent

__all__ = ["StorageAgent"]
