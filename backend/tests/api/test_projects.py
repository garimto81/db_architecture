"""
Project API Tests

Tests for /api/projects endpoints.
"""
import pytest
from uuid import uuid4


class TestListProjects:
    """Tests for GET /api/projects"""

    def test_list_projects_empty(self, client):
        """Should return empty list when no projects exist."""
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_projects_with_data(self, client, sample_project):
        """Should return projects list."""
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        assert data["items"][0]["code"] == "WSOP"
        assert data["items"][0]["name"] == "World Series of Poker"

    def test_list_projects_filter_active(self, client, sample_project, db_session):
        """Should filter by is_active status."""
        from src.models import Project

        # Add inactive project
        inactive = Project(
            id=uuid4(),
            code="HCL",
            name="Hustler Casino Live",
            is_active=False,
        )
        db_session.add(inactive)
        db_session.commit()

        # Filter active only
        response = client.get("/api/projects?is_active=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["code"] == "WSOP"

        # Filter inactive only
        response = client.get("/api/projects?is_active=false")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["code"] == "HCL"


class TestGetProject:
    """Tests for GET /api/projects/{id}"""

    def test_get_project_success(self, client, sample_project):
        """Should return project by ID."""
        response = client.get(f"/api/projects/{sample_project.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_project.id)
        assert data["code"] == "WSOP"

    def test_get_project_not_found(self, client):
        """Should return 404 for non-existent project."""
        fake_id = uuid4()
        response = client.get(f"/api/projects/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"


class TestGetProjectStats:
    """Tests for GET /api/projects/{id}/stats"""

    def test_get_stats_empty_project(self, client, sample_project):
        """Should return zero counts for project without data."""
        response = client.get(f"/api/projects/{sample_project.id}/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["project_code"] == "WSOP"
        assert data["total_seasons"] == 0
        assert data["total_events"] == 0
        assert data["total_episodes"] == 0
        assert data["total_video_files"] == 0

    def test_get_stats_with_data(self, client, full_hierarchy):
        """Should return correct counts for project with data."""
        project = full_hierarchy["project"]
        response = client.get(f"/api/projects/{project.id}/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_seasons"] == 1
        assert data["total_events"] == 1
        assert data["total_episodes"] == 1
        assert data["total_video_files"] == 1
        assert data["total_duration_hours"] == 2.0  # 7200 seconds = 2 hours
        assert data["total_size_gb"] > 0

    def test_get_stats_not_found(self, client):
        """Should return 404 for non-existent project."""
        fake_id = uuid4()
        response = client.get(f"/api/projects/{fake_id}/stats")
        assert response.status_code == 404
