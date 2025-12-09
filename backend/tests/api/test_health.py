"""
Health API Tests

Tests for /api/health endpoints.
"""
import pytest


class TestDatabaseHealth:
    """Tests for GET /api/health/db"""

    def test_health_check_success(self, client):
        """Should return healthy status when DB is connected."""
        response = client.get("/api/health/db")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["database"]["connected"] is True
        assert data["database"]["response_time_ms"] >= 0
        assert "tables" in data["database"]

    def test_health_check_has_table_counts(self, client, sample_project):
        """Should return table counts."""
        response = client.get("/api/health/db")
        assert response.status_code == 200
        data = response.json()

        tables = data["database"]["tables"]
        assert tables["projects"] == 1
        assert tables["seasons"] == 0
        assert tables["events"] == 0

    def test_health_check_with_full_hierarchy(self, client, full_hierarchy):
        """Should return correct counts with data."""
        response = client.get("/api/health/db")
        assert response.status_code == 200
        data = response.json()

        tables = data["database"]["tables"]
        assert tables["projects"] == 1
        assert tables["seasons"] == 1
        assert tables["events"] == 1
        assert tables["episodes"] == 1
        assert tables["video_files"] == 1


class TestTableDetails:
    """Tests for GET /api/health/db/tables"""

    def test_table_details_empty(self, client):
        """Should return zero counts when empty."""
        response = client.get("/api/health/db/tables")
        assert response.status_code == 200
        data = response.json()

        assert data["projects"]["total"] == 0
        assert data["seasons"]["total"] == 0
        assert data["video_files"]["total_size_gb"] == 0.0

    def test_table_details_with_data(self, client, full_hierarchy):
        """Should return detailed stats with data."""
        response = client.get("/api/health/db/tables")
        assert response.status_code == 200
        data = response.json()

        assert data["projects"]["total"] == 1
        assert data["projects"]["active"] == 1
        assert data["video_files"]["total"] == 1
        assert data["video_files"]["total_size_gb"] > 0
        assert data["video_files"]["total_duration_hours"] == 2.0


class TestConnectionInfo:
    """Tests for GET /api/health/db/connections"""

    def test_connection_info(self, client):
        """Should return connection info or graceful error for SQLite."""
        response = client.get("/api/health/db/connections")
        assert response.status_code == 200
        data = response.json()

        # SQLite doesn't support pg_stat_activity, so we expect a message
        assert "message" in data or "active_connections" in data
