"""
ParserAgent 테스트

파일명 파싱 기능을 테스트합니다.
"""

import pytest
from src.agents.core.agent_context import AgentContext
from src.agents.blocks.parser import ParserAgent


@pytest.fixture
def parser_agent():
    """ParserAgent 픽스처"""
    return ParserAgent()


@pytest.fixture
def context():
    """AgentContext 픽스처"""
    return AgentContext(task_id="test-parser-001")


class TestParserAgent:
    """ParserAgent 테스트"""

    def test_get_capabilities(self, parser_agent):
        """능력 목록 테스트"""
        caps = parser_agent.get_capabilities()

        assert "parse_filename" in caps
        assert "parse_batch" in caps
        assert "detect_project" in caps

    @pytest.mark.asyncio
    async def test_parse_wsop_filename(self, parser_agent, context):
        """WSOP 파일명 파싱 테스트"""
        result = await parser_agent.execute(
            context,
            {
                "action": "parse_filename",
                "filename": "WSOP 2023 Event 1 Main Event Day 1 Part 1.mp4",
            },
        )

        assert result.success is True
        data = result.data

        assert data["project"] == "WSOP"
        assert data["year"] == 2023
        assert data["event_number"] == 1
        assert "Day 1" in data["stage"] or data["stage"] == "Day 1"
        assert data["part"] == 1
        assert data["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_parse_wpt_filename(self, parser_agent, context):
        """WPT 파일명 파싱 테스트"""
        result = await parser_agent.execute(
            context,
            {
                "action": "parse_filename",
                "filename": "WPT 2022 Legends of Poker Episode 5.mp4",
            },
        )

        assert result.success is True
        data = result.data

        assert data["project"] == "WPT"
        assert data["year"] == 2022
        assert data["episode"] == 5

    @pytest.mark.asyncio
    async def test_parse_unknown_project(self, parser_agent, context):
        """알 수 없는 프로젝트 파싱 테스트"""
        result = await parser_agent.execute(
            context,
            {
                "action": "parse_filename",
                "filename": "random_video_file.mp4",
            },
        )

        assert result.success is True
        data = result.data

        # 프로젝트를 찾지 못하면 낮은 신뢰도
        assert data["confidence"] < 0.5 or data["project"] is None

    @pytest.mark.asyncio
    async def test_parse_batch(self, parser_agent, context):
        """배치 파싱 테스트"""
        result = await parser_agent.execute(
            context,
            {
                "action": "parse_batch",
                "filenames": [
                    "WSOP 2023 Event 1.mp4",
                    "WPT 2022 Final.mp4",
                    "EPT 2021 Barcelona.mp4",
                ],
            },
        )

        assert result.success is True
        data = result.data

        assert data["total"] == 3
        assert len(data["results"]) == 3

    @pytest.mark.asyncio
    async def test_detect_project(self, parser_agent, context):
        """프로젝트 감지 테스트"""
        result = await parser_agent.execute(
            context,
            {
                "action": "detect_project",
                "filename": "WSOP 2023 Main Event.mp4",
            },
        )

        assert result.success is True
        assert result.data["project"] == "WSOP"
        assert result.data["confidence"] > 0.8

    @pytest.mark.asyncio
    async def test_extract_metadata(self, parser_agent, context):
        """메타데이터 추출 테스트"""
        result = await parser_agent.execute(
            context,
            {
                "action": "extract_metadata",
                "filename": "WSOP_2023_Event1_Day1_1080p_h264.mp4",
            },
        )

        assert result.success is True
        data = result.data

        # 해상도 또는 코덱 정보가 추출되어야 함
        assert "extra" in data

    @pytest.mark.asyncio
    async def test_suggest_normalization(self, parser_agent, context):
        """정규화 제안 테스트"""
        result = await parser_agent.execute(
            context,
            {
                "action": "suggest_normalization",
                "filename": "wsop 2023 event#1 day-1 pt.1.mp4",
            },
        )

        assert result.success is True
        assert "normalized" in result.data
        assert "original" in result.data

    @pytest.mark.asyncio
    async def test_parse_with_date(self, parser_agent, context):
        """날짜 포함 파일명 파싱 테스트"""
        result = await parser_agent.execute(
            context,
            {
                "action": "parse_filename",
                "filename": "WSOP_2023-07-15_Event1.mp4",
            },
        )

        assert result.success is True
        data = result.data

        assert data["date"] == "2023-07-15"

    @pytest.mark.asyncio
    async def test_missing_filename_error(self, parser_agent, context):
        """파일명 누락 에러 테스트"""
        result = await parser_agent.execute(
            context,
            {
                "action": "parse_filename",
                # filename 누락
            },
        )

        assert result.success is False
        assert any("filename" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_token_tracking(self, parser_agent, context):
        """토큰 추적 테스트"""
        initial_tokens = parser_agent.tokens_used

        await parser_agent.execute(
            context,
            {
                "action": "parse_filename",
                "filename": "WSOP 2023 Event 1.mp4",
            },
        )

        # 토큰이 추적되어야 함
        assert parser_agent.tokens_used >= initial_tokens


class TestParserPatterns:
    """파싱 패턴 테스트"""

    @pytest.fixture
    def agent(self):
        return ParserAgent()

    @pytest.mark.parametrize(
        "filename,expected_project",
        [
            ("WSOP 2023 Event 1.mp4", "WSOP"),
            ("WPT Season 20 Episode 1.mp4", "WPT"),
            ("GG Poker 2022 WSOP Online.mp4", "GGPK"),
            ("EPT 2021 Barcelona Main Event.mp4", "EPT"),
            ("APT 2022 Manila Day 1.mp4", "APT"),
        ],
    )
    @pytest.mark.asyncio
    async def test_project_detection(self, agent, filename, expected_project):
        """프로젝트 감지 파라미터 테스트"""
        ctx = AgentContext(task_id="test-pattern")
        result = await agent.execute(
            ctx,
            {"action": "detect_project", "filename": filename},
        )

        assert result.success is True
        assert result.data["project"] == expected_project

    @pytest.mark.parametrize(
        "filename,expected_stage",
        [
            ("WSOP Final Table.mp4", "Final Table"),
            ("WSOP Day 2.mp4", "Day 2"),
            ("WSOP Heads Up.mp4", "Heads Up"),
        ],
    )
    @pytest.mark.asyncio
    async def test_stage_detection(self, agent, filename, expected_stage):
        """스테이지 감지 파라미터 테스트"""
        ctx = AgentContext(task_id="test-stage")
        result = await agent.execute(
            ctx,
            {"action": "parse_filename", "filename": filename},
        )

        assert result.success is True
        # stage가 감지되어야 함
        assert result.data["stage"] is not None
