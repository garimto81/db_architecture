"""
Scheduler API Routes

Endpoints for managing automated sync schedules.
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services.scheduler_service import get_scheduler


router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


# ============== Schemas ==============

class SchedulerStatusResponse(BaseModel):
    """Scheduler status response"""
    available: bool
    running: bool
    jobs: list
    history: Dict[str, Any]


class SchedulesResponse(BaseModel):
    """Available schedules response"""
    schedules: Dict[str, Dict[str, Any]]


class JobActionResponse(BaseModel):
    """Job action response"""
    success: bool
    message: str
    job_id: Optional[str] = None


class AddJobRequest(BaseModel):
    """Request to add a custom job"""
    job_id: str = Field(..., description="Unique job identifier")
    cron_expression: str = Field(..., description="Cron expression (e.g., '0 * * * *')")
    name: Optional[str] = Field(None, description="Human-readable job name")


# ============== Endpoints ==============

@router.get("/status", response_model=SchedulerStatusResponse)
def get_scheduler_status() -> SchedulerStatusResponse:
    """
    Get scheduler status and job information.

    Returns current running state, registered jobs, and execution history.
    """
    scheduler = get_scheduler()
    status = scheduler.get_status()

    return SchedulerStatusResponse(
        available=status['available'],
        running=status['running'],
        jobs=status['jobs'],
        history=status['history'],
    )


@router.get("/schedules", response_model=SchedulesResponse)
def get_schedules() -> SchedulesResponse:
    """
    Get configured schedule definitions.

    Returns default schedule configurations including cron expressions.
    """
    scheduler = get_scheduler()
    schedules = scheduler.get_schedules()

    return SchedulesResponse(schedules=schedules)


@router.post("/start", response_model=JobActionResponse)
def start_scheduler() -> JobActionResponse:
    """
    Start the scheduler with default jobs.

    Registers NAS scan, Sheet sync, and validation jobs.
    """
    scheduler = get_scheduler()

    if not scheduler.is_available:
        raise HTTPException(
            status_code=503,
            detail="APScheduler not installed. Run: pip install apscheduler"
        )

    success = scheduler.start()

    return JobActionResponse(
        success=success,
        message="Scheduler started" if success else "Failed to start scheduler",
    )


@router.post("/stop", response_model=JobActionResponse)
def stop_scheduler() -> JobActionResponse:
    """
    Stop the scheduler.

    Gracefully shuts down all scheduled jobs.
    """
    scheduler = get_scheduler()
    success = scheduler.stop()

    return JobActionResponse(
        success=success,
        message="Scheduler stopped" if success else "Scheduler was not running",
    )


@router.post("/jobs/{job_id}/trigger", response_model=JobActionResponse)
def trigger_job(job_id: str) -> JobActionResponse:
    """
    Trigger immediate execution of a scheduled job.

    **Valid job IDs**: nas_scan, sheet_sync, daily_validation
    """
    scheduler = get_scheduler()

    if not scheduler.is_available:
        raise HTTPException(
            status_code=503,
            detail="APScheduler not installed"
        )

    success = scheduler.trigger_job(job_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )

    return JobActionResponse(
        success=True,
        message=f"Job {job_id} triggered",
        job_id=job_id,
    )


@router.post("/jobs/{job_id}/pause", response_model=JobActionResponse)
def pause_job(job_id: str) -> JobActionResponse:
    """
    Pause a scheduled job.

    The job will not run until resumed.
    """
    scheduler = get_scheduler()

    if not scheduler.is_available:
        raise HTTPException(
            status_code=503,
            detail="APScheduler not installed"
        )

    success = scheduler.pause_job(job_id)

    return JobActionResponse(
        success=success,
        message=f"Job {job_id} paused" if success else f"Failed to pause {job_id}",
        job_id=job_id,
    )


@router.post("/jobs/{job_id}/resume", response_model=JobActionResponse)
def resume_job(job_id: str) -> JobActionResponse:
    """
    Resume a paused job.
    """
    scheduler = get_scheduler()

    if not scheduler.is_available:
        raise HTTPException(
            status_code=503,
            detail="APScheduler not installed"
        )

    success = scheduler.resume_job(job_id)

    return JobActionResponse(
        success=success,
        message=f"Job {job_id} resumed" if success else f"Failed to resume {job_id}",
        job_id=job_id,
    )


@router.delete("/jobs/{job_id}", response_model=JobActionResponse)
def remove_job(job_id: str) -> JobActionResponse:
    """
    Remove a job from the scheduler.
    """
    scheduler = get_scheduler()

    if not scheduler.is_available:
        raise HTTPException(
            status_code=503,
            detail="APScheduler not installed"
        )

    success = scheduler.remove_job(job_id)

    return JobActionResponse(
        success=success,
        message=f"Job {job_id} removed" if success else f"Job not found: {job_id}",
        job_id=job_id,
    )
