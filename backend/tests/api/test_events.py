"""
Event API Tests

Tests for /api/events endpoints.
"""
import pytest
from uuid import uuid4


class TestListEvents:
    """Tests for GET /api/events"""

    def test_list_events_empty(self, client):
        """Should return empty list when no events exist."""
        response = client.get("/api/events")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    def test_list_events_with_data(self, client, sample_event, sample_season, sample_project):
        """Should return events list with parent info."""
        response = client.get("/api/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        event = data["items"][0]
        assert event["name"] == "$10,000 No-Limit Hold'em Main Event"
        assert event["event_type"] == "main_event"
        assert event["game_type"] == "NLHE"
        # Check parent info is included
        assert event["season_name"] == "WSOP 2024"
        assert event["season_year"] == 2024
        assert event["project_code"] == "WSOP"

    def test_list_events_filter_by_season(self, client, sample_event, sample_season):
        """Should filter events by season_id."""
        # Filter by existing season
        response = client.get(f"/api/events?season_id={sample_season.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

        # Filter by non-existent season
        fake_id = uuid4()
        response = client.get(f"/api/events?season_id={fake_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0

    def test_list_events_filter_by_event_type(self, client, sample_event, sample_season, sample_project):
        """Should filter events by event_type."""
        response = client.get("/api/events?event_type=main_event")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

        response = client.get("/api/events?event_type=cash_game")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0

    def test_list_events_pagination(self, client, sample_event, sample_season, sample_project):
        """Should support pagination parameters."""
        response = client.get("/api/events?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10


class TestGetEvent:
    """Tests for GET /api/events/{id}"""

    def test_get_event_success(self, client, sample_event, sample_season, sample_project):
        """Should return event with full details."""
        response = client.get(f"/api/events/{sample_event.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_event.id)
        assert data["name"] == "$10,000 No-Limit Hold'em Main Event"
        # Decimal serializes with 2 decimal places
        assert float(data["buy_in"]) == 10000.0
        assert data["season_name"] == "WSOP 2024"
        assert data["project_code"] == "WSOP"
        assert data["episode_count"] == 0

    def test_get_event_with_episodes(self, client, full_hierarchy):
        """Should return correct episode count."""
        event = full_hierarchy["event"]
        response = client.get(f"/api/events/{event.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["episode_count"] == 1

    def test_get_event_not_found(self, client):
        """Should return 404 for non-existent event."""
        fake_id = uuid4()
        response = client.get(f"/api/events/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Event not found"


class TestGetEventEpisodes:
    """Tests for GET /api/events/{id}/episodes"""

    def test_get_episodes_empty(self, client, sample_event, sample_season, sample_project):
        """Should return empty list when no episodes exist."""
        response = client.get(f"/api/events/{sample_event.id}/episodes")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_episodes_with_data(self, client, full_hierarchy):
        """Should return episodes for event."""
        event = full_hierarchy["event"]
        response = client.get(f"/api/events/{event.id}/episodes")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        episode = data["items"][0]
        assert episode["title"] == "Main Event Day 1 - Part 1"
        assert episode["episode_number"] == 1
        assert episode["duration_seconds"] == 7200


class TestGetEpisodeVideoFiles:
    """Tests for GET /api/episodes/{id}/video-files"""

    def test_get_video_files_empty(self, client, sample_episode, sample_event, sample_season, sample_project):
        """Should return empty list when no video files exist."""
        response = client.get(f"/api/episodes/{sample_episode.id}/video-files")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_video_files_with_data(self, client, full_hierarchy):
        """Should return video files for episode."""
        episode = full_hierarchy["episode"]
        response = client.get(f"/api/episodes/{episode.id}/video-files")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        video = data[0]
        assert video["file_name"] == "day1_part1.mp4"
        assert video["resolution"] == "1920x1080"
        assert video["version_type"] == "clean"
        assert video["is_original"] is True

    def test_get_video_files_not_found(self, client):
        """Should return empty list for non-existent episode."""
        fake_id = uuid4()
        response = client.get(f"/api/episodes/{fake_id}/video-files")
        assert response.status_code == 200
        data = response.json()
        assert data == []
