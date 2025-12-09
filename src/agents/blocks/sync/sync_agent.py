"""
SyncAgent - 파일 시스템 동기화 전담 에이전트

NAS(SMB)와 GCS 파일 시스템을 스캔하고 동기화합니다.

주요 기능:
- NAS 디렉토리 스캔
- GCS 버킷 스캔
- 소스 간 비교 및 diff 생성
- 파일 동기화 (메타데이터 기준)
"""

import os
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import asyncio

from ...core.base_agent import BaseAgent
from ...core.agent_context import AgentContext
from ...core.agent_result import AgentResult
from ...core.exceptions import AgentExecutionError


@dataclass
class FileInfo:
    """파일 정보"""

    path: str
    filename: str
    size: int = 0
    modified_time: Optional[datetime] = None
    source: str = "unknown"  # "nas", "gcs"
    checksum: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "filename": self.filename,
            "size": self.size,
            "modified_time": self.modified_time.isoformat() if self.modified_time else None,
            "source": self.source,
            "checksum": self.checksum,
            "extra": self.extra,
        }


@dataclass
class SyncDiff:
    """동기화 차이점"""

    source_only: List[FileInfo] = field(default_factory=list)
    target_only: List[FileInfo] = field(default_factory=list)
    modified: List[Dict[str, FileInfo]] = field(default_factory=list)
    identical: List[FileInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_only": [f.to_dict() for f in self.source_only],
            "target_only": [f.to_dict() for f in self.target_only],
            "modified": [
                {"source": m["source"].to_dict(), "target": m["target"].to_dict()}
                for m in self.modified
            ],
            "identical_count": len(self.identical),
        }


class SyncAgent(BaseAgent):
    """
    파일 시스템 동기화 전담 에이전트

    NAS와 GCS 파일 시스템을 스캔하고 동기화합니다.

    사용법:
        agent = SyncAgent()
        result = await agent.execute(context, {
            "action": "scan_nas",
            "path": "//NAS/poker-vod",
            "extensions": [".mp4", ".mkv"]
        })

    Capabilities:
        - scan_nas: NAS 디렉토리 스캔
        - scan_gcs: GCS 버킷 스캔 (시뮬레이션)
        - scan_local: 로컬 디렉토리 스캔
        - compare_sources: 두 소스 간 비교
        - generate_sync_plan: 동기화 계획 생성
    """

    # 지원 확장자
    DEFAULT_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v"}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 에이전트 설정
                - nas_root: NAS 루트 경로
                - gcs_bucket: GCS 버킷 이름
                - extensions: 스캔할 파일 확장자 목록
                - max_depth: 최대 스캔 깊이
        """
        super().__init__("BLOCK_SYNC", config)

        self._nas_root = self.config.get("nas_root", "")
        self._gcs_bucket = self.config.get("gcs_bucket", "")
        self._extensions = set(self.config.get("extensions", self.DEFAULT_EXTENSIONS))
        self._max_depth = self.config.get("max_depth", 10)

    def get_capabilities(self) -> List[str]:
        """에이전트 능력 목록"""
        return [
            "scan_nas",
            "scan_gcs",
            "scan_local",
            "compare_sources",
            "generate_sync_plan",
        ]

    async def execute(
        self, context: AgentContext, input_data: Dict[str, Any]
    ) -> AgentResult:
        """
        메인 실행 로직

        Args:
            context: 실행 컨텍스트
            input_data: 입력 데이터
                - action: 수행할 액션
                - path: 스캔 경로
                - extensions: 파일 확장자 필터

        Returns:
            AgentResult: 스캔/동기화 결과
        """
        try:
            await self.pre_execute(context)

            action = input_data.get("action", "scan_local")

            if action == "scan_nas":
                result = await self._scan_nas(input_data)
            elif action == "scan_gcs":
                result = await self._scan_gcs(input_data)
            elif action == "scan_local":
                result = await self._scan_local(input_data)
            elif action == "compare_sources":
                result = await self._compare_sources(input_data)
            elif action == "generate_sync_plan":
                result = await self._generate_sync_plan(input_data)
            else:
                raise AgentExecutionError(
                    f"Unknown action: {action}", self.block_id
                )

            await self.post_execute(result)
            return result

        except Exception as e:
            return await self.handle_error(e, context)

    async def _scan_nas(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        NAS 디렉토리 스캔

        SMB 네트워크 경로를 스캔합니다.
        실제 환경에서는 SMB 라이브러리 사용 필요.
        """
        path = input_data.get("path", self._nas_root)
        extensions = set(input_data.get("extensions", self._extensions))

        if not path:
            return AgentResult.failure_result(
                errors=["NAS path is required"],
                error_type="ValidationError",
            )

        # NAS 경로는 실제 환경에서 SMB 마운트 또는 라이브러리 필요
        # 여기서는 로컬 스캔으로 폴백
        self.logger.info(f"Scanning NAS path: {path}")

        files = await self._do_scan(path, extensions, source="nas")

        self._track_tokens(len(files) * 10)  # 파일당 약 10토큰 추정

        return AgentResult.success_result(
            data={
                "files": [f.to_dict() for f in files],
                "total": len(files),
                "source": "nas",
                "path": path,
            },
            metrics={
                "files_scanned": len(files),
                "total_size": sum(f.size for f in files),
            },
        )

    async def _scan_gcs(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        GCS 버킷 스캔

        Google Cloud Storage 버킷을 스캔합니다.
        실제 환경에서는 google-cloud-storage 라이브러리 사용.
        """
        bucket = input_data.get("bucket", self._gcs_bucket)
        prefix = input_data.get("prefix", "")
        extensions = set(input_data.get("extensions", self._extensions))

        if not bucket:
            return AgentResult.failure_result(
                errors=["GCS bucket name is required"],
                error_type="ValidationError",
            )

        self.logger.info(f"Scanning GCS bucket: {bucket}, prefix: {prefix}")

        # GCS 스캔 시뮬레이션 (실제 구현 시 google-cloud-storage 사용)
        # 여기서는 빈 결과 반환
        files: List[FileInfo] = []

        # 실제 구현 예시:
        # from google.cloud import storage
        # client = storage.Client()
        # bucket_obj = client.bucket(bucket)
        # blobs = bucket_obj.list_blobs(prefix=prefix)
        # for blob in blobs:
        #     if any(blob.name.lower().endswith(ext) for ext in extensions):
        #         files.append(FileInfo(...))

        return AgentResult.success_result(
            data={
                "files": [f.to_dict() for f in files],
                "total": len(files),
                "source": "gcs",
                "bucket": bucket,
                "prefix": prefix,
            },
            warnings=["GCS scan is simulated - integrate google-cloud-storage for production"],
            metrics={"files_scanned": len(files)},
        )

    async def _scan_local(self, input_data: Dict[str, Any]) -> AgentResult:
        """로컬 디렉토리 스캔"""
        path = input_data.get("path", "")
        extensions = set(input_data.get("extensions", self._extensions))

        if not path:
            return AgentResult.failure_result(
                errors=["Local path is required"],
                error_type="ValidationError",
            )

        # 범위 체크
        self._check_scope(path)

        self.logger.info(f"Scanning local path: {path}")

        files = await self._do_scan(path, extensions, source="local")

        self._track_tokens(len(files) * 10)

        return AgentResult.success_result(
            data={
                "files": [f.to_dict() for f in files],
                "total": len(files),
                "source": "local",
                "path": path,
            },
            metrics={
                "files_scanned": len(files),
                "total_size": sum(f.size for f in files),
            },
        )

    async def _compare_sources(self, input_data: Dict[str, Any]) -> AgentResult:
        """두 소스 간 비교"""
        source_files = input_data.get("source_files", [])
        target_files = input_data.get("target_files", [])

        if not source_files:
            return AgentResult.failure_result(
                errors=["source_files is required"],
                error_type="ValidationError",
            )

        # FileInfo 객체로 변환 (이미 dict인 경우)
        source_infos = [
            FileInfo(**f) if isinstance(f, dict) else f for f in source_files
        ]
        target_infos = [
            FileInfo(**f) if isinstance(f, dict) else f for f in target_files
        ]

        # 파일명 기준 매핑
        source_map = {f.filename: f for f in source_infos}
        target_map = {f.filename: f for f in target_infos}

        diff = SyncDiff()

        # 소스에만 있는 파일
        for filename, file_info in source_map.items():
            if filename not in target_map:
                diff.source_only.append(file_info)

        # 타겟에만 있는 파일
        for filename, file_info in target_map.items():
            if filename not in source_map:
                diff.target_only.append(file_info)

        # 양쪽에 있는 파일 비교
        for filename in source_map.keys() & target_map.keys():
            source_file = source_map[filename]
            target_file = target_map[filename]

            # 크기 또는 수정 시간으로 비교
            if source_file.size != target_file.size:
                diff.modified.append({"source": source_file, "target": target_file})
            else:
                diff.identical.append(source_file)

        self._track_tokens(len(source_files) + len(target_files))

        return AgentResult.success_result(
            data=diff.to_dict(),
            metrics={
                "source_only": len(diff.source_only),
                "target_only": len(diff.target_only),
                "modified": len(diff.modified),
                "identical": len(diff.identical),
            },
        )

    async def _generate_sync_plan(self, input_data: Dict[str, Any]) -> AgentResult:
        """동기화 계획 생성"""
        diff_data = input_data.get("diff", {})
        strategy = input_data.get("strategy", "source_wins")  # source_wins, target_wins, newer_wins

        if not diff_data:
            return AgentResult.failure_result(
                errors=["diff data is required"],
                error_type="ValidationError",
            )

        plan = {
            "strategy": strategy,
            "actions": [],
            "summary": {
                "to_copy": 0,
                "to_update": 0,
                "to_delete": 0,
            },
        }

        # 소스에만 있는 파일 -> 복사
        for file_data in diff_data.get("source_only", []):
            plan["actions"].append({
                "action": "copy",
                "source": file_data.get("path"),
                "reason": "file_exists_only_in_source",
            })
            plan["summary"]["to_copy"] += 1

        # 수정된 파일 -> 업데이트 (전략에 따라)
        for mod_data in diff_data.get("modified", []):
            plan["actions"].append({
                "action": "update",
                "source": mod_data.get("source", {}).get("path"),
                "target": mod_data.get("target", {}).get("path"),
                "reason": "file_modified",
            })
            plan["summary"]["to_update"] += 1

        # 타겟에만 있는 파일 처리 (전략에 따라)
        if strategy == "source_wins":
            for file_data in diff_data.get("target_only", []):
                plan["actions"].append({
                    "action": "delete",
                    "target": file_data.get("path"),
                    "reason": "file_not_in_source",
                })
                plan["summary"]["to_delete"] += 1

        self._track_tokens(len(plan["actions"]) * 5)

        return AgentResult.success_result(
            data=plan,
            metrics=plan["summary"],
        )

    async def _do_scan(
        self, path: str, extensions: Set[str], source: str
    ) -> List[FileInfo]:
        """
        실제 디렉토리 스캔

        Args:
            path: 스캔 경로
            extensions: 필터링할 확장자
            source: 소스 타입

        Returns:
            파일 정보 목록
        """
        files: List[FileInfo] = []
        base_path = Path(path)

        if not base_path.exists():
            self.logger.warning(f"Path does not exist: {path}")
            return files

        # 비동기 실행을 위해 executor 사용
        def scan_sync():
            result = []
            depth = 0
            for root, dirs, filenames in os.walk(base_path):
                # 깊이 제한
                current_depth = len(Path(root).relative_to(base_path).parts)
                if current_depth > self._max_depth:
                    dirs.clear()
                    continue

                for filename in filenames:
                    ext = Path(filename).suffix.lower()
                    if ext in extensions:
                        file_path = Path(root) / filename
                        try:
                            stat = file_path.stat()
                            result.append(
                                FileInfo(
                                    path=str(file_path),
                                    filename=filename,
                                    size=stat.st_size,
                                    modified_time=datetime.fromtimestamp(stat.st_mtime),
                                    source=source,
                                )
                            )
                        except OSError as e:
                            self.logger.warning(f"Cannot stat file {file_path}: {e}")

            return result

        # 별도 스레드에서 실행
        loop = asyncio.get_event_loop()
        files = await loop.run_in_executor(None, scan_sync)

        return files
