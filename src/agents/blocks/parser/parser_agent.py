"""
ParserAgent - 파일명 파싱 전담 에이전트

파일명에서 메타데이터를 추출하고 프로젝트(대회)를 감지합니다.

주요 기능:
- 파일명 파싱 (WSOP, WPT, GGPK 등 패턴 인식)
- 프로젝트/대회 감지
- 메타데이터 추출 (날짜, 이벤트, 스테이지 등)
- 정규화된 데이터 구조 생성
"""

import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ...core.base_agent import BaseAgent
from ...core.agent_context import AgentContext
from ...core.agent_result import AgentResult
from ...core.exceptions import AgentExecutionError


@dataclass
class ParsedMetadata:
    """파싱된 메타데이터"""

    filename: str
    project: Optional[str] = None
    year: Optional[int] = None
    event_name: Optional[str] = None
    event_number: Optional[int] = None
    stage: Optional[str] = None  # "Day1", "Final Table" 등
    part: Optional[int] = None
    episode: Optional[int] = None
    date: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    raw_match: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "filename": self.filename,
            "project": self.project,
            "year": self.year,
            "event_name": self.event_name,
            "event_number": self.event_number,
            "stage": self.stage,
            "part": self.part,
            "episode": self.episode,
            "date": self.date,
            "extra": self.extra,
            "confidence": self.confidence,
            "raw_match": self.raw_match,
        }


class ParserAgent(BaseAgent):
    """
    파일명 파싱 전담 에이전트

    파일명에서 포커 대회 정보를 추출합니다.

    지원 프로젝트:
    - WSOP (World Series of Poker)
    - WPT (World Poker Tour)
    - GGPK (GG Poker)
    - EPT (European Poker Tour)
    - APT (Asian Poker Tour)
    - 일반 VOD

    사용법:
        agent = ParserAgent()
        result = await agent.execute(context, {
            "action": "parse_filename",
            "filename": "WSOP 2023 Event 1 Day 1 Part 1.mp4"
        })

    Capabilities:
        - parse_filename: 단일 파일명 파싱
        - parse_batch: 다중 파일명 일괄 파싱
        - detect_project: 프로젝트(대회) 감지
        - extract_metadata: 상세 메타데이터 추출
        - suggest_normalization: 정규화된 파일명 제안
    """

    # 프로젝트 패턴 정의 (컴파일된 정규식)
    PROJECT_PATTERNS = {
        "WSOP": re.compile(
            r"WSOP\s*(?P<year>\d{4})?\s*"
            r"(?:Event\s*#?(?P<event_num>\d+))?\s*"
            r"(?P<event_name>[^-]+?)?\s*"
            r"(?:Day\s*(?P<day>\d+))?\s*"
            r"(?:Part\s*(?P<part>\d+))?",
            re.IGNORECASE,
        ),
        "WPT": re.compile(
            r"WPT\s*(?P<year>\d{4})?\s*"
            r"(?P<event_name>[^-]+?)?\s*"
            r"(?:Ep(?:isode)?\s*(?P<episode>\d+))?\s*"
            r"(?:Part\s*(?P<part>\d+))?",
            re.IGNORECASE,
        ),
        "GGPK": re.compile(
            r"(?:GG\s*(?:Poker)?|GGPK)\s*"
            r"(?P<year>\d{4})?\s*"
            r"(?P<event_name>[^-]+?)?\s*"
            r"(?:Part\s*(?P<part>\d+))?",
            re.IGNORECASE,
        ),
        "EPT": re.compile(
            r"EPT\s*(?P<year>\d{4})?\s*"
            r"(?P<location>[A-Za-z]+)?\s*"
            r"(?P<event_name>[^-]+?)?\s*"
            r"(?:Day\s*(?P<day>\d+))?",
            re.IGNORECASE,
        ),
        "APT": re.compile(
            r"APT\s*(?P<year>\d{4})?\s*"
            r"(?P<event_name>[^-]+?)?\s*"
            r"(?:Day\s*(?P<day>\d+))?",
            re.IGNORECASE,
        ),
    }

    # 스테이지 패턴
    STAGE_PATTERNS = [
        (re.compile(r"Final\s*Table", re.IGNORECASE), "Final Table"),
        (re.compile(r"Day\s*(\d+)", re.IGNORECASE), "Day {0}"),
        (re.compile(r"Heads?\s*Up", re.IGNORECASE), "Heads Up"),
        (re.compile(r"Bubble", re.IGNORECASE), "Bubble"),
        (re.compile(r"ITM|In\s*The\s*Money", re.IGNORECASE), "ITM"),
    ]

    # 날짜 패턴
    DATE_PATTERNS = [
        re.compile(r"(\d{4})[-_](\d{2})[-_](\d{2})"),  # YYYY-MM-DD
        re.compile(r"(\d{2})[-_](\d{2})[-_](\d{4})"),  # DD-MM-YYYY
        re.compile(r"(\d{4})(\d{2})(\d{2})"),  # YYYYMMDD
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 에이전트 설정
                - strict_mode: 엄격한 파싱 모드 (기본: False)
                - min_confidence: 최소 신뢰도 (기본: 0.5)
        """
        super().__init__("BLOCK_PARSER", config)

        self._strict_mode = self.config.get("strict_mode", False)
        self._min_confidence = self.config.get("min_confidence", 0.5)

    def get_capabilities(self) -> List[str]:
        """에이전트 능력 목록"""
        return [
            "parse_filename",
            "parse_batch",
            "detect_project",
            "extract_metadata",
            "suggest_normalization",
        ]

    async def execute(
        self, context: AgentContext, input_data: Dict[str, Any]
    ) -> AgentResult:
        """
        메인 실행 로직

        Args:
            context: 실행 컨텍스트
            input_data: 입력 데이터
                - action: 수행할 액션 (parse_filename, parse_batch, detect_project)
                - filename: 파일명 (단일)
                - filenames: 파일명 목록 (배치)

        Returns:
            AgentResult: 파싱 결과
        """
        try:
            await self.pre_execute(context)

            action = input_data.get("action", "parse_filename")

            if action == "parse_filename":
                result = await self._parse_filename(input_data)
            elif action == "parse_batch":
                result = await self._parse_batch(input_data)
            elif action == "detect_project":
                result = await self._detect_project(input_data)
            elif action == "extract_metadata":
                result = await self._extract_metadata(input_data)
            elif action == "suggest_normalization":
                result = await self._suggest_normalization(input_data)
            else:
                raise AgentExecutionError(
                    f"Unknown action: {action}", self.block_id
                )

            await self.post_execute(result)
            return result

        except Exception as e:
            return await self.handle_error(e, context)

    async def _parse_filename(self, input_data: Dict[str, Any]) -> AgentResult:
        """단일 파일명 파싱"""
        filename = input_data.get("filename", "")
        if not filename:
            return AgentResult.failure_result(
                errors=["filename is required"],
                error_type="ValidationError",
            )

        # 토큰 추적
        self._track_tokens(self._estimate_tokens(filename))

        parsed = self._do_parse(filename)

        return AgentResult.success_result(
            data=parsed.to_dict(),
            metrics={"confidence": parsed.confidence},
        )

    async def _parse_batch(self, input_data: Dict[str, Any]) -> AgentResult:
        """다중 파일명 일괄 파싱"""
        filenames = input_data.get("filenames", [])
        if not filenames:
            return AgentResult.failure_result(
                errors=["filenames list is required"],
                error_type="ValidationError",
            )

        results = []
        warnings = []

        for filename in filenames:
            self._track_tokens(self._estimate_tokens(filename))
            parsed = self._do_parse(filename)

            if parsed.confidence < self._min_confidence:
                warnings.append(f"Low confidence for: {filename}")

            results.append(parsed.to_dict())

        return AgentResult.success_result(
            data={"results": results, "total": len(results)},
            warnings=warnings,
            metrics={
                "total_parsed": len(results),
                "low_confidence_count": len(warnings),
            },
        )

    async def _detect_project(self, input_data: Dict[str, Any]) -> AgentResult:
        """프로젝트(대회) 감지"""
        filename = input_data.get("filename", "")
        if not filename:
            return AgentResult.failure_result(
                errors=["filename is required"],
                error_type="ValidationError",
            )

        self._track_tokens(self._estimate_tokens(filename))

        project = None
        confidence = 0.0

        for project_name, pattern in self.PROJECT_PATTERNS.items():
            match = pattern.search(filename)
            if match:
                project = project_name
                confidence = 0.9
                break

        if not project:
            # 키워드 기반 추측
            filename_lower = filename.lower()
            if "poker" in filename_lower:
                project = "GENERAL_POKER"
                confidence = 0.5
            else:
                project = "UNKNOWN"
                confidence = 0.3

        return AgentResult.success_result(
            data={"project": project, "confidence": confidence},
            metrics={"confidence": confidence},
        )

    async def _extract_metadata(self, input_data: Dict[str, Any]) -> AgentResult:
        """상세 메타데이터 추출"""
        filename = input_data.get("filename", "")
        if not filename:
            return AgentResult.failure_result(
                errors=["filename is required"],
                error_type="ValidationError",
            )

        self._track_tokens(self._estimate_tokens(filename))

        parsed = self._do_parse(filename)

        # 추가 메타데이터 추출
        extra = {}

        # 파일 확장자
        if "." in filename:
            extra["extension"] = filename.rsplit(".", 1)[-1].lower()

        # 해상도 감지
        resolution_match = re.search(
            r"(\d{3,4})[pP]|(\d{3,4})x(\d{3,4})", filename
        )
        if resolution_match:
            if resolution_match.group(1):
                extra["resolution"] = f"{resolution_match.group(1)}p"
            else:
                extra["resolution"] = (
                    f"{resolution_match.group(2)}x{resolution_match.group(3)}"
                )

        # 코덱 감지
        codec_patterns = ["h264", "h265", "hevc", "x264", "x265", "av1"]
        for codec in codec_patterns:
            if codec in filename.lower():
                extra["codec"] = codec
                break

        parsed.extra.update(extra)

        return AgentResult.success_result(
            data=parsed.to_dict(),
            metrics={"fields_extracted": len([v for v in parsed.to_dict().values() if v])},
        )

    async def _suggest_normalization(self, input_data: Dict[str, Any]) -> AgentResult:
        """정규화된 파일명 제안"""
        filename = input_data.get("filename", "")
        if not filename:
            return AgentResult.failure_result(
                errors=["filename is required"],
                error_type="ValidationError",
            )

        self._track_tokens(self._estimate_tokens(filename))

        parsed = self._do_parse(filename)

        # 정규화된 이름 생성
        parts = []

        if parsed.project:
            parts.append(parsed.project)
        if parsed.year:
            parts.append(str(parsed.year))
        if parsed.event_name:
            parts.append(parsed.event_name.strip())
        if parsed.event_number:
            parts.append(f"Event{parsed.event_number}")
        if parsed.stage:
            parts.append(parsed.stage)
        if parsed.part:
            parts.append(f"Part{parsed.part}")

        if parts:
            normalized = "_".join(parts)
            # 확장자 유지
            if "." in filename:
                ext = filename.rsplit(".", 1)[-1]
                normalized = f"{normalized}.{ext}"
        else:
            normalized = filename

        return AgentResult.success_result(
            data={
                "original": filename,
                "normalized": normalized,
                "parsed": parsed.to_dict(),
            },
        )

    def _do_parse(self, filename: str) -> ParsedMetadata:
        """
        실제 파싱 로직

        Args:
            filename: 파싱할 파일명

        Returns:
            ParsedMetadata: 파싱 결과
        """
        result = ParsedMetadata(filename=filename)
        confidence_factors = []

        # 1. 프로젝트 패턴 매칭
        for project_name, pattern in self.PROJECT_PATTERNS.items():
            match = pattern.search(filename)
            if match:
                result.project = project_name
                result.raw_match = match.group(0)
                confidence_factors.append(0.4)

                # 그룹에서 데이터 추출
                groups = match.groupdict()

                if groups.get("year"):
                    try:
                        result.year = int(groups["year"])
                        confidence_factors.append(0.15)
                    except ValueError:
                        pass

                if groups.get("event_num"):
                    try:
                        result.event_number = int(groups["event_num"])
                        confidence_factors.append(0.1)
                    except ValueError:
                        pass

                if groups.get("event_name"):
                    result.event_name = groups["event_name"].strip()
                    confidence_factors.append(0.1)

                if groups.get("day"):
                    result.stage = f"Day {groups['day']}"
                    confidence_factors.append(0.1)

                if groups.get("part"):
                    try:
                        result.part = int(groups["part"])
                        confidence_factors.append(0.05)
                    except ValueError:
                        pass

                if groups.get("episode"):
                    try:
                        result.episode = int(groups["episode"])
                        confidence_factors.append(0.05)
                    except ValueError:
                        pass

                break

        # 2. 스테이지 패턴 매칭 (프로젝트와 별개로)
        if not result.stage:
            for stage_pattern, stage_template in self.STAGE_PATTERNS:
                stage_match = stage_pattern.search(filename)
                if stage_match:
                    if stage_match.groups():
                        result.stage = stage_template.format(*stage_match.groups())
                    else:
                        result.stage = stage_template
                    confidence_factors.append(0.05)
                    break

        # 3. 날짜 패턴 매칭
        for date_pattern in self.DATE_PATTERNS:
            date_match = date_pattern.search(filename)
            if date_match:
                groups = date_match.groups()
                if len(groups) == 3:
                    # YYYY-MM-DD 형식으로 정규화
                    if len(groups[0]) == 4:
                        result.date = f"{groups[0]}-{groups[1]}-{groups[2]}"
                    else:
                        result.date = f"{groups[2]}-{groups[1]}-{groups[0]}"

                    # 연도 추출 (없으면)
                    if not result.year:
                        try:
                            year = int(groups[0]) if len(groups[0]) == 4 else int(groups[2])
                            if 2000 <= year <= 2030:
                                result.year = year
                        except ValueError:
                            pass

                    confidence_factors.append(0.1)
                break

        # 4. 신뢰도 계산
        result.confidence = min(1.0, sum(confidence_factors))

        # 프로젝트를 찾지 못한 경우 낮은 신뢰도
        if not result.project:
            result.confidence = min(result.confidence, 0.3)

        return result
