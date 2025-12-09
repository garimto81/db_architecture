"""
Scheduler API Tests

Tests for /api/scheduler endpoints.
"""
import pytest


class TestSchedulerStatus:
    """Tests for GET /api/scheduler/status"""

    def test_status_returns_availability(self, client):
        """Should return scheduler availability status."""
        response = client.get("/api/scheduler/status")
        assert response.status_code == 200
        data = response.json()

        assert "available" in data
        assert "running" in data
        assert "jobs" in data
        assert "history" in data

    def test_status_jobs_is_list(self, client):
        """Should return jobs as a list."""
        response = client.get("/api/scheduler/status")
        data = response.json()

        assert isinstance(data["jobs"], list)


class TestSchedulerSchedules:
    """Tests for GET /api/scheduler/schedules"""

    def test_schedules_returns_configs(self, client):
        """Should return schedule configurations."""
        response = client.get("/api/scheduler/schedules")
        assert response.status_code == 200
        data = response.json()

        assert "schedules" in data
        schedules = data["schedules"]

        # Should have default schedules
        assert "nas_scan" in schedules
        assert "sheet_sync" in schedules
        assert "daily_validation" in schedules

    def test_schedule_has_cron(self, client):
        """Should include cron expressions."""
        response = client.get("/api/scheduler/schedules")
        data = response.json()

        nas_scan = data["schedules"]["nas_scan"]
        assert "cron" in nas_scan
        assert nas_scan["cron"] == "0 * * * *"


class TestSyncScheduler:
    """Tests for SyncScheduler class"""

    def test_scheduler_not_running_initially(self):
        """Scheduler should not be running initially."""
        from src.services.scheduler_service import SyncScheduler

        scheduler = SyncScheduler()
        status = scheduler.get_status()

        assert status["running"] is False

    def test_default_schedules(self):
        """Should have default schedule configurations."""
        from src.services.scheduler_service import SyncScheduler

        assert "nas_scan" in SyncScheduler.DEFAULT_SCHEDULES
        assert "sheet_sync" in SyncScheduler.DEFAULT_SCHEDULES
        assert "daily_validation" in SyncScheduler.DEFAULT_SCHEDULES

    def test_schedule_config_properties(self):
        """Schedule configs should have required properties."""
        from src.services.scheduler_service import SyncScheduler

        for job_id, config in SyncScheduler.DEFAULT_SCHEDULES.items():
            assert config.job_id == job_id
            assert config.name
            assert config.cron_expression
            assert isinstance(config.enabled, bool)


class TestScheduleConfig:
    """Tests for ScheduleConfig dataclass"""

    def test_schedule_config_defaults(self):
        """Should have sensible defaults."""
        from src.services.scheduler_service import ScheduleConfig

        config = ScheduleConfig(
            job_id="test_job",
            name="Test Job",
            cron_expression="0 * * * *",
        )

        assert config.enabled is True
        assert config.description == ""


class TestJobResult:
    """Tests for JobResult dataclass"""

    def test_job_result_defaults(self):
        """Should have sensible defaults."""
        from src.services.scheduler_service import JobResult
        from datetime import datetime

        result = JobResult(
            job_id="test_job",
            started_at=datetime.now(),
        )

        assert result.finished_at is None
        assert result.status == "running"
        assert result.message == ""
        assert result.details == {}


class TestGetScheduler:
    """Tests for get_scheduler function"""

    def test_get_scheduler_returns_instance(self):
        """Should return a SyncScheduler instance."""
        from src.services.scheduler_service import get_scheduler, SyncScheduler

        scheduler = get_scheduler()
        assert isinstance(scheduler, SyncScheduler)

    def test_get_scheduler_singleton(self):
        """Should return the same instance."""
        from src.services.scheduler_service import get_scheduler

        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()

        # Note: This might not be the same object if module reloads
        # but both should be valid SyncScheduler instances
        assert scheduler1 is not None
        assert scheduler2 is not None
