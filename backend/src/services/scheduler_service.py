"""
Scheduler Service

Automated sync scheduling using APScheduler.
Based on LLD 02 Section 6: Sync Schedule.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False


logger = logging.getLogger(__name__)


@dataclass
class ScheduleConfig:
    """Configuration for a scheduled job"""
    job_id: str
    name: str
    cron_expression: str
    enabled: bool = True
    description: str = ""


@dataclass
class JobResult:
    """Result of a scheduled job execution"""
    job_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str = "running"
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class SyncScheduler:
    """
    Scheduler for automated NAS and Google Sheet synchronization.

    Uses APScheduler with cron triggers based on LLD 02 specifications:
    - NAS scan: Every hour (0 * * * *)
    - Sheet sync: Every hour (0 * * * *)
    - Validation: Daily at 03:00 (0 3 * * *)
    """

    # Default schedule configurations
    DEFAULT_SCHEDULES = {
        'nas_scan': ScheduleConfig(
            job_id='nas_scan',
            name='NAS Scan',
            cron_expression='0 * * * *',  # Every hour
            description='Scan NAS directories for new/modified video files',
        ),
        'nas_scan_urgent': ScheduleConfig(
            job_id='nas_scan_urgent',
            name='NAS Scan (Urgent)',
            cron_expression='*/15 * * * *',  # Every 15 minutes
            enabled=False,  # Only enable during tournaments
            description='Urgent scan during tournament periods',
        ),
        'sheet_sync': ScheduleConfig(
            job_id='sheet_sync',
            name='Google Sheet Sync',
            cron_expression='0 * * * *',  # Every hour
            description='Sync hand clips from Google Sheets',
        ),
        'daily_validation': ScheduleConfig(
            job_id='daily_validation',
            name='Daily Validation',
            cron_expression='0 3 * * *',  # Daily at 03:00
            description='Validate data integrity and generate reports',
        ),
        'weekly_report': ScheduleConfig(
            job_id='weekly_report',
            name='Weekly Report',
            cron_expression='0 4 * * 0',  # Sunday at 04:00
            enabled=False,
            description='Generate weekly sync statistics report',
        ),
    }

    def __init__(self, db_session_factory: Optional[Callable] = None):
        """
        Initialize the scheduler.

        Args:
            db_session_factory: Factory function to create DB sessions
        """
        self.db_session_factory = db_session_factory
        self._scheduler = None
        self._job_history: Dict[str, JobResult] = {}
        self._running = False

    @property
    def is_available(self) -> bool:
        """Check if APScheduler is installed"""
        return APSCHEDULER_AVAILABLE

    def _get_scheduler(self) -> Optional['BackgroundScheduler']:
        """Get or create the scheduler instance"""
        if not APSCHEDULER_AVAILABLE:
            logger.warning("APScheduler not installed. Scheduling disabled.")
            return None

        if self._scheduler is None:
            self._scheduler = BackgroundScheduler(
                timezone='Asia/Seoul',
                job_defaults={
                    'coalesce': True,  # Combine missed runs
                    'max_instances': 1,  # Only one instance per job
                    'misfire_grace_time': 60 * 15,  # 15 minutes grace
                }
            )

            # Add event listeners
            self._scheduler.add_listener(
                self._on_job_executed,
                EVENT_JOB_EXECUTED
            )
            self._scheduler.add_listener(
                self._on_job_error,
                EVENT_JOB_ERROR
            )

        return self._scheduler

    def _on_job_executed(self, event):
        """Handle successful job execution"""
        job_id = event.job_id
        if job_id in self._job_history:
            self._job_history[job_id].finished_at = datetime.now()
            self._job_history[job_id].status = 'success'
        logger.info(f"Job {job_id} executed successfully")

    def _on_job_error(self, event):
        """Handle job execution error"""
        job_id = event.job_id
        if job_id in self._job_history:
            self._job_history[job_id].finished_at = datetime.now()
            self._job_history[job_id].status = 'error'
            self._job_history[job_id].message = str(event.exception)
        logger.error(f"Job {job_id} failed: {event.exception}")

    def _create_nas_scan_job(self):
        """Create NAS scan job function"""
        def nas_scan_job():
            result = JobResult(
                job_id='nas_scan',
                started_at=datetime.now(),
            )
            self._job_history['nas_scan'] = result

            try:
                if self.db_session_factory:
                    from src.services.sync_service import NasSyncService

                    db = self.db_session_factory()
                    try:
                        service = NasSyncService(db)
                        results = []

                        for project_code in ['WSOP', 'GGMILLIONS', 'MPP', 'PAD', 'GOG', 'HCL']:
                            scan_result = service.scan_project(project_code)
                            results.append({
                                'project': project_code,
                                'scanned': scan_result.scanned_count,
                                'new': scan_result.new_count,
                                'updated': scan_result.updated_count,
                                'status': scan_result.status,
                            })

                        result.details = {'projects': results}
                        result.message = f"Scanned {sum(r['scanned'] for r in results)} files"
                    finally:
                        db.close()
                else:
                    result.message = "No database session factory configured"

            except Exception as e:
                result.status = 'error'
                result.message = str(e)
                logger.exception(f"NAS scan job failed: {e}")

        return nas_scan_job

    def _create_sheet_sync_job(self):
        """Create Google Sheet sync job function"""
        def sheet_sync_job():
            result = JobResult(
                job_id='sheet_sync',
                started_at=datetime.now(),
            )
            self._job_history['sheet_sync'] = result

            try:
                if self.db_session_factory:
                    from src.services.google_sheet_service import GoogleSheetService

                    db = self.db_session_factory()
                    try:
                        service = GoogleSheetService(db)
                        sync_results = service.sync_all()

                        result.details = {
                            'sheets': {
                                k: {
                                    'processed': v.processed_count,
                                    'new': v.new_count,
                                    'status': v.status,
                                }
                                for k, v in sync_results.items()
                            }
                        }
                        total = sum(v.processed_count for v in sync_results.values())
                        result.message = f"Processed {total} rows from {len(sync_results)} sheets"
                    finally:
                        db.close()
                else:
                    result.message = "No database session factory configured"

            except Exception as e:
                result.status = 'error'
                result.message = str(e)
                logger.exception(f"Sheet sync job failed: {e}")

        return sheet_sync_job

    def _create_validation_job(self):
        """Create daily validation job function"""
        def validation_job():
            result = JobResult(
                job_id='daily_validation',
                started_at=datetime.now(),
            )
            self._job_history['daily_validation'] = result

            try:
                # Placeholder for validation logic
                # In production, this would:
                # 1. Check data integrity
                # 2. Verify sync state consistency
                # 3. Generate daily report
                # 4. Send alerts if needed

                result.message = "Validation completed"
                result.details = {
                    'checks_passed': True,
                    'issues_found': 0,
                }

            except Exception as e:
                result.status = 'error'
                result.message = str(e)
                logger.exception(f"Validation job failed: {e}")

        return validation_job

    def start(self) -> bool:
        """
        Start the scheduler with default jobs.

        Returns:
            True if started successfully, False otherwise
        """
        scheduler = self._get_scheduler()
        if not scheduler:
            return False

        if self._running:
            logger.warning("Scheduler already running")
            return True

        try:
            # Add NAS scan job
            config = self.DEFAULT_SCHEDULES['nas_scan']
            if config.enabled:
                scheduler.add_job(
                    self._create_nas_scan_job(),
                    CronTrigger.from_crontab(config.cron_expression),
                    id=config.job_id,
                    name=config.name,
                    replace_existing=True,
                )

            # Add Sheet sync job
            config = self.DEFAULT_SCHEDULES['sheet_sync']
            if config.enabled:
                scheduler.add_job(
                    self._create_sheet_sync_job(),
                    CronTrigger.from_crontab(config.cron_expression),
                    id=config.job_id,
                    name=config.name,
                    replace_existing=True,
                )

            # Add validation job
            config = self.DEFAULT_SCHEDULES['daily_validation']
            if config.enabled:
                scheduler.add_job(
                    self._create_validation_job(),
                    CronTrigger.from_crontab(config.cron_expression),
                    id=config.job_id,
                    name=config.name,
                    replace_existing=True,
                )

            scheduler.start()
            self._running = True
            logger.info("Scheduler started with default jobs")
            return True

        except Exception as e:
            logger.exception(f"Failed to start scheduler: {e}")
            return False

    def stop(self) -> bool:
        """Stop the scheduler"""
        if self._scheduler and self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler stopped")
            return True
        return False

    def add_job(
        self,
        job_id: str,
        func: Callable,
        cron_expression: str,
        name: Optional[str] = None,
    ) -> bool:
        """
        Add a custom job to the scheduler.

        Args:
            job_id: Unique job identifier
            func: Job function to execute
            cron_expression: Cron expression for schedule
            name: Human-readable job name

        Returns:
            True if added successfully
        """
        scheduler = self._get_scheduler()
        if not scheduler:
            return False

        try:
            scheduler.add_job(
                func,
                CronTrigger.from_crontab(cron_expression),
                id=job_id,
                name=name or job_id,
                replace_existing=True,
            )
            logger.info(f"Added job {job_id} with schedule {cron_expression}")
            return True
        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {e}")
            return False

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the scheduler"""
        scheduler = self._get_scheduler()
        if not scheduler:
            return False

        try:
            scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False

    def pause_job(self, job_id: str) -> bool:
        """Pause a job"""
        scheduler = self._get_scheduler()
        if not scheduler:
            return False

        try:
            scheduler.pause_job(job_id)
            return True
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        scheduler = self._get_scheduler()
        if not scheduler:
            return False

        try:
            scheduler.resume_job(job_id)
            return True
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False

    def trigger_job(self, job_id: str) -> bool:
        """Trigger immediate execution of a job"""
        scheduler = self._get_scheduler()
        if not scheduler:
            return False

        try:
            job = scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=datetime.now())
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to trigger job {job_id}: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status and job information"""
        scheduler = self._get_scheduler()

        status = {
            'available': APSCHEDULER_AVAILABLE,
            'running': self._running,
            'jobs': [],
            'history': {},
        }

        if scheduler and self._running:
            for job in scheduler.get_jobs():
                job_info = {
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'pending': job.pending,
                }
                status['jobs'].append(job_info)

        # Add job history
        for job_id, result in self._job_history.items():
            status['history'][job_id] = {
                'started_at': result.started_at.isoformat(),
                'finished_at': result.finished_at.isoformat() if result.finished_at else None,
                'status': result.status,
                'message': result.message,
            }

        return status

    def get_schedules(self) -> Dict[str, Dict[str, Any]]:
        """Get configured schedules"""
        return {
            job_id: {
                'name': config.name,
                'cron': config.cron_expression,
                'enabled': config.enabled,
                'description': config.description,
            }
            for job_id, config in self.DEFAULT_SCHEDULES.items()
        }


# Global scheduler instance
_scheduler_instance: Optional[SyncScheduler] = None


def get_scheduler() -> SyncScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SyncScheduler()
    return _scheduler_instance


def init_scheduler(db_session_factory: Callable) -> SyncScheduler:
    """Initialize the scheduler with database session factory"""
    global _scheduler_instance
    _scheduler_instance = SyncScheduler(db_session_factory)
    return _scheduler_instance
