"""
Test Google Sheet Service - Issue #30: Nas Folder Link → video_file_id 연결

TDD Red Phase: 이 테스트들은 아직 통과하지 않음 (구현 전)
"""
import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch


class TestNasPathNormalizer:
    """NasPathNormalizer 경로 정규화 테스트"""

    def test_normalize_unc_path_to_windows_drive(self):
        """UNC 경로 → Windows 드라이브 경로 변환"""
        from src.services.google_sheet_service import NasPathNormalizer

        unc_path = r"\\10.10.100.122\docker\GGPNAs\ARCHIVE\WSOP\2024\video.mp4"
        expected = r"Z:\GGPNAs\ARCHIVE\WSOP\2024\video.mp4"

        result = NasPathNormalizer.normalize(unc_path)

        assert result == expected

    def test_normalize_docker_path_to_windows_drive(self):
        """Docker 마운트 경로 → Windows 드라이브 경로 변환"""
        from src.services.google_sheet_service import NasPathNormalizer

        docker_path = "/nas/ARCHIVE/WSOP/2024/video.mp4"
        expected = r"Z:\GGPNAs\ARCHIVE\WSOP\2024\video.mp4"

        result = NasPathNormalizer.normalize(docker_path)

        assert result == expected

    def test_normalize_maintains_backslash_for_db(self):
        """경로는 백슬래시 유지 (DB 형식)"""
        from src.services.google_sheet_service import NasPathNormalizer

        path_with_backslash = r"Z:\GGPNAs\ARCHIVE\WSOP\video.mp4"
        expected = r"Z:\GGPNAs\ARCHIVE\WSOP\video.mp4"

        result = NasPathNormalizer.normalize(path_with_backslash)

        assert result == expected

    def test_normalize_empty_path(self):
        """빈 경로 처리"""
        from src.services.google_sheet_service import NasPathNormalizer

        result = NasPathNormalizer.normalize("")
        assert result == ""

        result = NasPathNormalizer.normalize(None)
        assert result == ""

    def test_to_db_path_alias(self):
        """to_db_path()는 normalize()와 동일하게 동작"""
        from src.services.google_sheet_service import NasPathNormalizer

        path = r"\\10.10.100.122\docker\GGPNAs\ARCHIVE\test.mp4"

        assert NasPathNormalizer.to_db_path(path) == NasPathNormalizer.normalize(path)


class TestVideoFileMatcher:
    """VideoFileMatcher video_file_id 매칭 테스트"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return MagicMock()

    @pytest.fixture
    def sample_video_file_id(self):
        return uuid4()

    def test_find_video_file_id_exact_match(self, mock_db_session, sample_video_file_id):
        """정확한 file_path 매칭"""
        from src.services.google_sheet_service import VideoFileMatcher

        # Mock DB query result
        mock_db_session.execute.return_value.first.return_value = (sample_video_file_id,)

        matcher = VideoFileMatcher(mock_db_session)
        nas_path = r"\\10.10.100.122\docker\GGPNAs\ARCHIVE\WSOP\video.mp4"

        result = matcher.find_video_file_id(nas_path)

        assert result == sample_video_file_id

    def test_find_video_file_id_empty_path(self, mock_db_session):
        """빈 경로 → None 반환"""
        from src.services.google_sheet_service import VideoFileMatcher

        matcher = VideoFileMatcher(mock_db_session)

        assert matcher.find_video_file_id("") is None
        assert matcher.find_video_file_id(None) is None

    def test_find_video_file_id_cache_hit(self, mock_db_session, sample_video_file_id):
        """캐시에서 조회 (DB 쿼리 없음)"""
        from src.services.google_sheet_service import VideoFileMatcher

        mock_db_session.execute.return_value.first.return_value = (sample_video_file_id,)

        matcher = VideoFileMatcher(mock_db_session)
        nas_path = r"\\10.10.100.122\docker\GGPNAs\ARCHIVE\WSOP\video.mp4"

        # 첫 번째 호출: DB 쿼리
        result1 = matcher.find_video_file_id(nas_path)
        # 두 번째 호출: 캐시 히트
        result2 = matcher.find_video_file_id(nas_path)

        assert result1 == result2 == sample_video_file_id
        # DB 쿼리는 한 번만 실행되어야 함
        assert mock_db_session.execute.call_count == 1

    def test_find_video_file_id_fallback_to_filename(self, mock_db_session, sample_video_file_id):
        """경로 매칭 실패 시 파일명으로 폴백"""
        from src.services.google_sheet_service import VideoFileMatcher

        # 첫 번째 쿼리 (정확한 경로): 실패
        # 두 번째 쿼리 (파일명): 성공
        mock_db_session.execute.return_value.first.side_effect = [
            None,  # 경로 매칭 실패
            (sample_video_file_id,),  # 파일명 매칭 성공
        ]

        matcher = VideoFileMatcher(mock_db_session)
        nas_path = r"\\10.10.100.122\docker\GGPNAs\ARCHIVE\WSOP\video.mp4"

        result = matcher.find_video_file_id(nas_path)

        assert result == sample_video_file_id
        assert mock_db_session.execute.call_count == 2

    def test_find_video_file_id_not_found(self, mock_db_session):
        """매칭 실패 → None 반환"""
        from src.services.google_sheet_service import VideoFileMatcher

        mock_db_session.execute.return_value.first.return_value = None

        matcher = VideoFileMatcher(mock_db_session)
        nas_path = r"\\10.10.100.122\docker\GGPNAs\ARCHIVE\WSOP\nonexistent.mp4"

        result = matcher.find_video_file_id(nas_path)

        assert result is None


class TestGoogleSheetServiceIntegration:
    """GoogleSheetService video_file_id 연결 통합 테스트"""

    @pytest.fixture
    def mock_db_session(self):
        return MagicMock()

    def test_parse_row_extracts_nas_path(self, mock_db_session):
        """_parse_row()가 nas_path (C열)를 추출"""
        from src.services.google_sheet_service import GoogleSheetService, SheetConfig

        service = GoogleSheetService(mock_db_session)

        # Metadata Archive 시트 구조
        row = [
            "1",                    # A: File No.
            "Test Title",           # B: File Name
            r"\\10.10.100.122\docker\GGPNAs\ARCHIVE\WSOP\test.mp4",  # C: Nas Folder Link
            "01:00:00",             # D: In
            "01:05:00",             # E: Out
            "★★★",                  # F: Hand Grade
        ]

        config = SheetConfig(
            sheet_id="test_sheet",
            sheet_name="Metadata Archive",
            source_type="metadata_archive",
            column_mapping=service.HAND_ANALYSIS_COLUMNS,
        )

        clip_data = service._parse_row(row, 1, config)

        # video_file_id가 clip_data에 포함되어야 함
        assert 'video_file_id' in clip_data

    def test_parse_row_matches_video_file_id(self, mock_db_session):
        """_parse_row()가 nas_path로 video_file_id를 매칭"""
        from src.services.google_sheet_service import GoogleSheetService, SheetConfig

        video_file_id = uuid4()

        # VideoFileMatcher mock
        with patch.object(
            GoogleSheetService,
            '__init__',
            lambda self, db, creds=None: None
        ):
            service = GoogleSheetService.__new__(GoogleSheetService)
            service.db = mock_db_session
            service.credentials_path = None
            service._client = None
            service._request_count = 0
            service._request_window_start = 0

            # video_matcher mock
            mock_matcher = MagicMock()
            mock_matcher.find_video_file_id.return_value = video_file_id
            service.video_matcher = mock_matcher

            row = [
                "1",
                "Test Title",
                r"\\10.10.100.122\docker\GGPNAs\ARCHIVE\WSOP\test.mp4",
                "01:00:00",
                "01:05:00",
                "★★★",
            ]

            config = SheetConfig(
                sheet_id="test_sheet",
                sheet_name="Metadata Archive",
                source_type="metadata_archive",
                column_mapping=GoogleSheetService.HAND_ANALYSIS_COLUMNS,
            )

            clip_data = service._parse_row(row, 1, config)

            assert clip_data['video_file_id'] == video_file_id
            mock_matcher.find_video_file_id.assert_called_once()

    def test_upsert_hand_clip_includes_video_file_id(self, mock_db_session):
        """_upsert_hand_clip()이 video_file_id를 DB에 저장"""
        from src.services.google_sheet_service import GoogleSheetService

        video_file_id = uuid4()

        # Insert case (existing is None)
        mock_db_session.execute.return_value.first.return_value = None

        service = GoogleSheetService(mock_db_session)

        clip_data = {
            'id': uuid4(),
            'sheet_source': 'metadata_archive',
            'sheet_row_number': 1,
            'title': 'Test',
            'timecode': '01:00:00',
            'timecode_end': '01:05:00',
            'hand_grade': '★★★',
            'notes': None,
            'video_file_id': video_file_id,
        }

        service._upsert_hand_clip(clip_data)

        # INSERT 쿼리에 video_file_id가 포함되어야 함
        insert_call = mock_db_session.execute.call_args_list[-1]
        query_params = insert_call[0][1]

        assert 'video_file_id' in query_params
        # video_file_id는 string으로 변환되어 저장됨
        assert query_params['video_file_id'] == str(video_file_id)


class TestPathNormalizationEdgeCases:
    """경로 정규화 엣지 케이스 테스트"""

    def test_normalize_double_backslash_unc(self):
        """이중 백슬래시 UNC 경로"""
        from src.services.google_sheet_service import NasPathNormalizer

        # Google Sheets에서 복사 시 이중 백슬래시가 올 수 있음
        path = r"\\\\10.10.100.122\\docker\\GGPNAs\\ARCHIVE\\test.mp4"
        result = NasPathNormalizer.normalize(path)

        assert r"Z:\GGPNAs\ARCHIVE" in result

    def test_normalize_mixed_slashes(self):
        """혼합 슬래시 경로"""
        from src.services.google_sheet_service import NasPathNormalizer

        path = r"\\10.10.100.122\docker/GGPNAs\ARCHIVE/test.mp4"
        result = NasPathNormalizer.normalize(path)

        # 모든 슬래시가 백슬래시로 변환 (DB 형식)
        assert "/" not in result

    def test_normalize_case_insensitive(self):
        """대소문자 무관 경로 처리"""
        from src.services.google_sheet_service import NasPathNormalizer

        path = r"\\10.10.100.122\Docker\GGPNas\ARCHIVE\test.mp4"
        result = NasPathNormalizer.normalize(path)

        assert result.startswith(r"Z:\GGPNAs\ARCHIVE")
