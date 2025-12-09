"""
Sync API Tests

Tests for /api/sync endpoints.
"""
import pytest
import tempfile
import os
from pathlib import Path


class TestSyncStatus:
    """Tests for GET /api/sync/status"""

    def test_sync_status_returns_projects(self, client, sample_project):
        """Should return sync status for all projects."""
        response = client.get("/api/sync/status")
        assert response.status_code == 200
        data = response.json()

        assert "projects" in data
        # Projects may be empty if not configured in NAS_PATHS


class TestSyncNas:
    """Tests for POST /api/sync/nas"""

    def test_sync_nas_invalid_project(self, client, sample_project):
        """Should handle invalid project codes gracefully."""
        response = client.post(
            "/api/sync/nas",
            json={"project_codes": ["INVALID_PROJECT"], "limit": 1}
        )
        assert response.status_code == 200
        data = response.json()

        # Should complete but with errors
        assert data["status"] == "completed"
        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "error"

    def test_sync_project_endpoint(self, client, sample_project):
        """Should validate project code."""
        # Invalid project code
        response = client.post("/api/sync/nas/INVALID")
        assert response.status_code == 400
        assert "Invalid project code" in response.json()["detail"]


class TestFileParser:
    """Tests for FileParser class"""

    def test_wsop_bracelet_pattern(self):
        """Should parse WSOP bracelet filenames."""
        from src.services.sync_service import FileParser

        parser = FileParser()

        # Create temp file for parsing
        with tempfile.NamedTemporaryFile(
            suffix=".mp4",
            prefix="10-wsop-2024-be-ev-21-25k-nlh-hr-ft-",
            delete=False
        ) as f:
            temp_path = f.name

        try:
            parsed = parser.parse(temp_path, "WSOP")

            assert parsed.project_code == "WSOP"
            assert parsed.file_name.endswith(".mp4")
        finally:
            os.unlink(temp_path)

    def test_version_type_detection(self):
        """Should detect version types from filenames."""
        from src.services.sync_service import FileParser

        parser = FileParser()

        # Test clean version
        with tempfile.NamedTemporaryFile(
            suffix=".mp4",
            prefix="video_clean_",
            delete=False
        ) as f:
            temp_path = f.name

        try:
            parsed = parser.parse(temp_path, "WSOP")
            assert parsed.version_type == "clean"
        finally:
            os.unlink(temp_path)

        # Test mastered version
        with tempfile.NamedTemporaryFile(
            suffix=".mp4",
            prefix="video_master_",
            delete=False
        ) as f:
            temp_path = f.name

        try:
            parsed = parser.parse(temp_path, "WSOP")
            assert parsed.version_type == "mastered"
        finally:
            os.unlink(temp_path)

    def test_video_extensions(self):
        """Should recognize video file extensions."""
        from src.services.sync_service import FileParser

        expected = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.mxf'}
        assert FileParser.VIDEO_EXTENSIONS == expected

    def test_game_type_mapping(self):
        """Should map game types correctly."""
        from src.services.sync_service import FileParser

        assert FileParser.GAME_TYPES['nlh'] == 'NLHE'
        assert FileParser.GAME_TYPES['plo'] == 'PLO'
        assert FileParser.GAME_TYPES['mixed'] == 'Mixed'


class TestParsedFile:
    """Tests for ParsedFile dataclass"""

    def test_parsed_file_defaults(self):
        """Should have sensible defaults."""
        from src.services.sync_service import ParsedFile
        from datetime import datetime

        parsed = ParsedFile(
            file_path="/test/file.mp4",
            file_name="file.mp4",
            file_size=1000,
            modified_time=datetime.now(),
            project_code="WSOP",
        )

        assert parsed.year is None
        assert parsed.event_number is None
        assert parsed.version_type is None
        assert parsed.duration_seconds is None


class TestScanResult:
    """Tests for ScanResult dataclass"""

    def test_scan_result_defaults(self):
        """Should have zero counts by default."""
        from src.services.sync_service import ScanResult

        result = ScanResult(project_code="WSOP")

        assert result.scanned_count == 0
        assert result.new_count == 0
        assert result.updated_count == 0
        assert result.error_count == 0
        assert result.errors == []
        assert result.status == "success"


# ============== Google Sheet Tests ==============

class TestTagNormalizer:
    """Tests for TagNormalizer class"""

    def test_normalize_preflop_allin(self):
        """Should normalize preflop all-in variations."""
        from src.services.google_sheet_service import TagNormalizer

        assert TagNormalizer.normalize("Preflop All-in") == "preflop_allin"
        assert TagNormalizer.normalize("preflop allin") == "preflop_allin"
        assert TagNormalizer.normalize("PREFLOP_ALLIN") == "preflop_allin"

    def test_normalize_bad_beat(self):
        """Should normalize bad beat variations."""
        from src.services.google_sheet_service import TagNormalizer

        assert TagNormalizer.normalize("Bad Beat") == "bad_beat"
        assert TagNormalizer.normalize("BADBEAT") == "bad_beat"
        assert TagNormalizer.normalize("bad-beat") == "bad_beat"

    def test_preserve_star_ratings(self):
        """Should preserve star ratings unchanged."""
        from src.services.google_sheet_service import TagNormalizer

        assert TagNormalizer.normalize("★★★") == "★★★"
        assert TagNormalizer.normalize("★★☆") == "★★☆"

    def test_normalize_list(self):
        """Should normalize comma-separated tags."""
        from src.services.google_sheet_service import TagNormalizer

        tags = "Bad Beat, Preflop All-in, cooler"
        result = TagNormalizer.normalize_list(tags)

        assert result == ["bad_beat", "preflop_allin", "cooler"]

    def test_normalize_empty(self):
        """Should handle empty input."""
        from src.services.google_sheet_service import TagNormalizer

        assert TagNormalizer.normalize("") == ""
        assert TagNormalizer.normalize_list("") == []


class TestSheetSyncResult:
    """Tests for SheetSyncResult dataclass"""

    def test_sheet_sync_result_defaults(self):
        """Should have zero counts by default."""
        from src.services.google_sheet_service import SheetSyncResult

        result = SheetSyncResult(sheet_id="test-sheet")

        assert result.processed_count == 0
        assert result.new_count == 0
        assert result.updated_count == 0
        assert result.error_count == 0
        assert result.errors == []
        assert result.status == "success"


class TestGoogleSheetService:
    """Tests for GoogleSheetService"""

    def test_sheet_configs_exist(self):
        """Should have default sheet configs."""
        from src.services.google_sheet_service import GoogleSheetService

        assert 'hand_analysis' in GoogleSheetService.SHEET_CONFIGS
        assert 'hand_database' in GoogleSheetService.SHEET_CONFIGS

    def test_column_mappings(self):
        """Should have correct column mappings."""
        from src.services.google_sheet_service import GoogleSheetService

        # Hand analysis columns
        ha_cols = GoogleSheetService.HAND_ANALYSIS_COLUMNS
        assert 'timecode' in ha_cols
        assert 'title' in ha_cols
        assert 'tags' in ha_cols

        # Hand database columns
        hd_cols = GoogleSheetService.HAND_DATABASE_COLUMNS
        assert 'hand_id' in hd_cols
        assert 'video_title' in hd_cols
        assert 'pot_size' in hd_cols


class TestSheetSyncEndpoints:
    """Tests for /api/sync/sheets endpoints"""

    def test_sync_sheets_invalid_key(self, client, sample_project):
        """Should reject invalid sheet keys."""
        response = client.post("/api/sync/sheets/invalid_sheet")
        assert response.status_code == 400
        assert "Invalid sheet key" in response.json()["detail"]

    def test_sync_sheets_skipped_without_client(self, client, sample_project):
        """Should return skipped status when gspread is not configured."""
        response = client.post(
            "/api/sync/sheets",
            json={"sheet_keys": ["hand_analysis"], "limit": 1}
        )
        assert response.status_code == 200
        data = response.json()

        # Should complete but with skipped status (no gspread client)
        assert data["status"] == "completed"
        assert "hand_analysis" in data["results"]
