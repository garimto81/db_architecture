"""
Sync API Routes

Endpoints for NAS and Google Sheet synchronization operations.
Includes WebSocket broadcast integration for real-time progress updates.
"""
import uuid
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import get_db
from src.services.sync_service import NasSyncService, ScanResult
from src.services.google_sheet_service import GoogleSheetService, SheetSyncResult
from src.api.websocket import (
    broadcast_sync_start,
    broadcast_sync_progress,
    broadcast_sync_complete,
    broadcast_sync_error,
)


router = APIRouter(prefix="/api/sync", tags=["sync"])


# ============== Schemas ==============

class SyncRequest(BaseModel):
    """Request to trigger sync for specific projects"""
    project_codes: List[str] = Field(
        default=["WSOP", "GGMILLIONS", "MPP", "PAD", "GOG", "HCL"],
        description="Project codes to sync"
    )
    limit: Optional[int] = Field(
        default=None,
        description="Max files to process per project (for testing)"
    )


class SyncResultResponse(BaseModel):
    """Single project sync result"""
    project_code: str
    scanned_count: int
    new_count: int
    updated_count: int
    error_count: int
    errors: List[str]
    status: str


class SyncResponse(BaseModel):
    """Sync operation response"""
    status: str
    message: str
    results: List[SyncResultResponse]
    total_scanned: int
    total_new: int
    total_updated: int
    total_errors: int


class SyncStatusResponse(BaseModel):
    """Sync status for all projects"""
    projects: dict


# ============== Endpoints ==============

@router.post("/nas", response_model=SyncResponse)
def sync_nas(
    request: SyncRequest,
    db: Session = Depends(get_db),
) -> SyncResponse:
    """
    Synchronize NAS directories to database.

    Scans configured NAS paths for video files and upserts them to the database.
    Creates missing Season/Event/Episode hierarchy automatically.

    **Note**: This is a synchronous operation. For large directories,
    consider using the background sync endpoint.
    """
    service = NasSyncService(db)
    results = []

    for code in request.project_codes:
        result = service.scan_project(code, limit=request.limit)
        results.append(SyncResultResponse(
            project_code=result.project_code,
            scanned_count=result.scanned_count,
            new_count=result.new_count,
            updated_count=result.updated_count,
            error_count=result.error_count,
            errors=result.errors[:10],  # Limit errors in response
            status=result.status,
        ))

    total_scanned = sum(r.scanned_count for r in results)
    total_new = sum(r.new_count for r in results)
    total_updated = sum(r.updated_count for r in results)
    total_errors = sum(r.error_count for r in results)

    return SyncResponse(
        status="completed",
        message=f"Scanned {total_scanned} files, {total_new} new, {total_updated} updated",
        results=results,
        total_scanned=total_scanned,
        total_new=total_new,
        total_updated=total_updated,
        total_errors=total_errors,
    )


@router.post("/nas/{project_code}", response_model=SyncResultResponse)
def sync_project(
    project_code: str,
    limit: Optional[int] = Query(None, description="Max files to process"),
    db: Session = Depends(get_db),
) -> SyncResultResponse:
    """
    Synchronize a single project's NAS directory.

    **Valid project codes**: WSOP, GGMILLIONS, MPP, PAD, GOG, HCL
    """
    valid_codes = ["WSOP", "GGMILLIONS", "MPP", "PAD", "GOG", "HCL"]
    if project_code.upper() not in valid_codes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid project code. Valid codes: {', '.join(valid_codes)}"
        )

    service = NasSyncService(db)
    result = service.scan_project(project_code.upper(), limit=limit)

    return SyncResultResponse(
        project_code=result.project_code,
        scanned_count=result.scanned_count,
        new_count=result.new_count,
        updated_count=result.updated_count,
        error_count=result.error_count,
        errors=result.errors[:10],
        status=result.status,
    )


@router.get("/status", response_model=SyncStatusResponse)
def get_sync_status(
    db: Session = Depends(get_db),
) -> SyncStatusResponse:
    """
    Get sync status for all projects.

    Returns video file counts and NAS paths for each project.
    """
    service = NasSyncService(db)
    status = service.get_scan_status()

    return SyncStatusResponse(projects=status)


# Background sync (async pattern for large scans)
_sync_status = {"running": False, "last_result": None}


@router.post("/nas/background")
def sync_nas_background(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Start background NAS sync.

    Returns immediately. Check /api/sync/status for progress.
    """
    if _sync_status["running"]:
        raise HTTPException(
            status_code=409,
            detail="A sync operation is already in progress"
        )

    def run_sync():
        _sync_status["running"] = True
        try:
            service = NasSyncService(db)
            results = []
            for code in request.project_codes:
                result = service.scan_project(code, limit=request.limit)
                results.append(result)
            _sync_status["last_result"] = results
        finally:
            _sync_status["running"] = False

    background_tasks.add_task(run_sync)

    return {
        "status": "started",
        "message": f"Background sync started for {len(request.project_codes)} projects"
    }


# ============== Google Sheets Sync ==============

class SheetSyncRequest(BaseModel):
    """Request to sync Google Sheets"""
    sheet_keys: List[str] = Field(
        default=["hand_analysis", "hand_database"],
        description="Sheet keys to sync"
    )
    limit: Optional[int] = Field(
        default=None,
        description="Max rows to process per sheet (for testing)"
    )


class SheetSyncResultResponse(BaseModel):
    """Single sheet sync result"""
    sheet_id: str
    processed_count: int
    new_count: int
    updated_count: int
    error_count: int
    errors: List[str]
    status: str


class SheetSyncResponse(BaseModel):
    """Sheet sync operation response"""
    status: str
    message: str
    results: Dict[str, SheetSyncResultResponse]
    total_processed: int
    total_new: int
    total_updated: int


class SheetStatusResponse(BaseModel):
    """Google Sheets sync status"""
    sheets: Dict[str, Any]


@router.post("/sheets", response_model=SheetSyncResponse)
def sync_sheets(
    request: SheetSyncRequest,
    db: Session = Depends(get_db),
) -> SheetSyncResponse:
    """
    Synchronize Google Sheets to database.

    Syncs hand clip data from configured Google Sheets.
    Uses incremental sync based on row numbers.

    **Available sheet keys**: hand_analysis, hand_database
    """
    service = GoogleSheetService(db)
    results = {}

    for key in request.sheet_keys:
        result = service.sync_sheet(key, limit=request.limit)
        results[key] = SheetSyncResultResponse(
            sheet_id=result.sheet_id,
            processed_count=result.processed_count,
            new_count=result.new_count,
            updated_count=result.updated_count,
            error_count=result.error_count,
            errors=result.errors[:5],
            status=result.status,
        )

    total_processed = sum(r.processed_count for r in results.values())
    total_new = sum(r.new_count for r in results.values())
    total_updated = sum(r.updated_count for r in results.values())

    return SheetSyncResponse(
        status="completed",
        message=f"Processed {total_processed} rows, {total_new} new, {total_updated} updated",
        results=results,
        total_processed=total_processed,
        total_new=total_new,
        total_updated=total_updated,
    )


@router.post("/sheets/{sheet_key}", response_model=SheetSyncResultResponse)
def sync_single_sheet(
    sheet_key: str,
    limit: Optional[int] = Query(None, description="Max rows to process"),
    db: Session = Depends(get_db),
) -> SheetSyncResultResponse:
    """
    Synchronize a single Google Sheet.

    **Valid sheet keys**: hand_analysis, hand_database
    """
    valid_keys = ["hand_analysis", "hand_database"]
    if sheet_key not in valid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sheet key. Valid keys: {', '.join(valid_keys)}"
        )

    service = GoogleSheetService(db)
    result = service.sync_sheet(sheet_key, limit=limit)

    return SheetSyncResultResponse(
        sheet_id=result.sheet_id,
        processed_count=result.processed_count,
        new_count=result.new_count,
        updated_count=result.updated_count,
        error_count=result.error_count,
        errors=result.errors[:5],
        status=result.status,
    )


@router.get("/sheets/status", response_model=SheetStatusResponse)
def get_sheet_sync_status(
    db: Session = Depends(get_db),
) -> SheetStatusResponse:
    """
    Get sync status for all configured Google Sheets.

    Returns last sync time and row counts for each sheet.
    """
    service = GoogleSheetService(db)
    status = service.get_sync_status()

    return SheetStatusResponse(sheets=status)


# ============== Display Title Generation ==============

class DisplayTitleUpdateResponse(BaseModel):
    """Display title update result"""
    total: int
    updated: int
    errors: int
    error_details: List[str]


@router.post("/update-titles", response_model=DisplayTitleUpdateResponse)
def update_display_titles(
    db: Session = Depends(get_db),
) -> DisplayTitleUpdateResponse:
    """
    Update display_title for all video files that don't have one.

    Generates human-readable titles from filenames using TitleGenerator.
    Used for migrating existing data after adding display_title column.
    """
    service = NasSyncService(db)
    result = service.update_display_titles()

    return DisplayTitleUpdateResponse(
        total=result['total'],
        updated=result['updated'],
        errors=result['errors'],
        error_details=result['error_details'],
    )


# ============== Catalog Title Generation ==============

class CatalogTitleUpdateResponse(BaseModel):
    """Catalog title update result"""
    total: int
    updated: int
    errors: int
    error_details: List[str]


class CatalogItemsUpdateResponse(BaseModel):
    """Catalog items selection result"""
    total_files: int
    total_groups: int
    catalog_items: int
    duplicates_removed: int


@router.post("/update-catalog-titles", response_model=CatalogTitleUpdateResponse)
def update_catalog_titles(
    db: Session = Depends(get_db),
) -> CatalogTitleUpdateResponse:
    """
    Update catalog_title, episode_title, and content_type for all visible video files.

    Generates:
    - content_type: full_episode, hand_clip, highlight, etc.
    - catalog_title: Group title (e.g., "WSOP 2024 Main Event")
    - episode_title: Item title (e.g., "Day 1A" or "Ding vs Boianovsky")
    """
    service = NasSyncService(db)
    result = service.update_catalog_titles()

    return CatalogTitleUpdateResponse(
        total=result['total'],
        updated=result['updated'],
        errors=result['errors'],
        error_details=result['error_details'],
    )


@router.post("/update-catalog-items", response_model=CatalogItemsUpdateResponse)
def update_catalog_items(
    db: Session = Depends(get_db),
) -> CatalogItemsUpdateResponse:
    """
    Set is_catalog_item=True for representative files.

    Selects one file per catalog_title + episode_title group based on version priority:
    stream > clean > final_edit > mastered > nobug > generic > pgm > hires

    This removes duplicates from the catalog view.
    """
    service = NasSyncService(db)
    result = service.update_catalog_items()

    return CatalogItemsUpdateResponse(
        total_files=result['total_files'],
        total_groups=result['total_groups'],
        catalog_items=result['catalog_items'],
        duplicates_removed=result['duplicates_removed'],
    )


# ============== Frontend Trigger API ==============
# These endpoints are called by BLOCK_FRONTEND for manual sync triggers
# They integrate with WebSocket broadcasts for real-time progress

# In-memory storage for sync jobs (would use Redis in production)
_sync_jobs: Dict[str, Dict[str, Any]] = {}


class TriggerResponse(BaseModel):
    """Response for sync trigger"""
    sync_id: str


class SyncLogEntryResponse(BaseModel):
    """Sync log entry for frontend"""
    id: str
    timestamp: str
    source: str  # 'nas' or 'sheets'
    type: str  # 'start', 'complete', 'error'
    message: str
    details: Optional[Dict[str, Any]] = None


class SyncHistoryResponse(BaseModel):
    """Paginated sync history response"""
    items: List[SyncLogEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.post("/trigger/{source}", response_model=TriggerResponse)
async def trigger_sync(
    source: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> TriggerResponse:
    """
    Trigger manual sync for NAS or Google Sheets.

    Called by frontend sync panel for manual synchronization.
    Returns immediately with sync_id. Progress is sent via WebSocket.

    **source**: 'nas' or 'sheets'
    """
    valid_sources = ["nas", "sheets"]
    if source.lower() not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source. Valid sources: {', '.join(valid_sources)}"
        )

    # Check if sync is already running for this source
    for job_id, job in _sync_jobs.items():
        if job.get("source") == source and job.get("status") == "running":
            raise HTTPException(
                status_code=409,
                detail=f"A {source} sync is already in progress (id: {job_id})"
            )

    # Generate unique sync ID
    sync_id = str(uuid.uuid4())[:8]

    # Store job info
    _sync_jobs[sync_id] = {
        "id": sync_id,
        "source": source,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "triggered_by": "manual",
        "progress": {"current": 0, "total": 0, "percentage": 0},
        "result": None,
    }

    # Run sync in background with WebSocket broadcasts
    if source == "nas":
        background_tasks.add_task(_run_nas_sync_with_broadcast, sync_id, db)
    else:
        background_tasks.add_task(_run_sheets_sync_with_broadcast, sync_id, db)

    return TriggerResponse(sync_id=sync_id)


async def _run_nas_sync_with_broadcast(sync_id: str, db: Session):
    """Run NAS sync with WebSocket broadcast updates."""
    start_time = datetime.utcnow()

    try:
        # Broadcast start
        await broadcast_sync_start(sync_id, "nas", "manual")

        service = NasSyncService(db)
        project_codes = ["WSOP", "GGMILLIONS", "MPP", "PAD", "GOG", "HCL"]

        total_scanned = 0
        total_new = 0
        total_updated = 0
        total_errors = 0

        for i, code in enumerate(project_codes):
            # Broadcast progress for each project
            await broadcast_sync_progress(
                sync_id=sync_id,
                source="nas",
                current=i,
                total=len(project_codes),
                current_file=f"Scanning {code}...",
            )

            result = service.scan_project(code)
            total_scanned += result.scanned_count
            total_new += result.new_count
            total_updated += result.updated_count
            total_errors += result.error_count

        # Calculate duration
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Update job status
        _sync_jobs[sync_id]["status"] = "completed"
        _sync_jobs[sync_id]["completed_at"] = datetime.utcnow().isoformat()
        _sync_jobs[sync_id]["result"] = {
            "files_processed": total_scanned,
            "files_added": total_new,
            "files_updated": total_updated,
            "errors": total_errors,
        }

        # Broadcast completion
        await broadcast_sync_complete(
            sync_id=sync_id,
            source="nas",
            duration_ms=duration_ms,
            files_processed=total_scanned,
            files_added=total_new,
            files_updated=total_updated,
            errors=total_errors,
        )

    except Exception as e:
        _sync_jobs[sync_id]["status"] = "error"
        _sync_jobs[sync_id]["error"] = str(e)

        await broadcast_sync_error(
            sync_id=sync_id,
            source="nas",
            error_code="SYNC_FAILED",
            message=str(e),
        )


async def _run_sheets_sync_with_broadcast(sync_id: str, db: Session):
    """Run Google Sheets sync with WebSocket broadcast updates."""
    start_time = datetime.utcnow()

    try:
        # Broadcast start
        await broadcast_sync_start(sync_id, "sheets", "manual")

        service = GoogleSheetService(db)
        sheet_keys = ["hand_analysis", "hand_database"]

        total_processed = 0
        total_new = 0
        total_updated = 0
        total_errors = 0

        for i, key in enumerate(sheet_keys):
            # Broadcast progress
            await broadcast_sync_progress(
                sync_id=sync_id,
                source="sheets",
                current=i,
                total=len(sheet_keys),
                current_file=f"Syncing {key}...",
            )

            result = service.sync_sheet(key)
            total_processed += result.processed_count
            total_new += result.new_count
            total_updated += result.updated_count
            total_errors += result.error_count

        # Calculate duration
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Update job status
        _sync_jobs[sync_id]["status"] = "completed"
        _sync_jobs[sync_id]["completed_at"] = datetime.utcnow().isoformat()
        _sync_jobs[sync_id]["result"] = {
            "files_processed": total_processed,
            "files_added": total_new,
            "files_updated": total_updated,
            "errors": total_errors,
        }

        # Broadcast completion
        await broadcast_sync_complete(
            sync_id=sync_id,
            source="sheets",
            duration_ms=duration_ms,
            files_processed=total_processed,
            files_added=total_new,
            files_updated=total_updated,
            errors=total_errors,
        )

    except Exception as e:
        _sync_jobs[sync_id]["status"] = "error"
        _sync_jobs[sync_id]["error"] = str(e)

        await broadcast_sync_error(
            sync_id=sync_id,
            source="sheets",
            error_code="SYNC_FAILED",
            message=str(e),
        )


@router.get("/jobs/{sync_id}", response_model=SyncLogEntryResponse)
def get_sync_job(sync_id: str) -> SyncLogEntryResponse:
    """
    Get status of a specific sync job.

    Returns current status and result if completed.
    """
    if sync_id not in _sync_jobs:
        raise HTTPException(
            status_code=404,
            detail=f"Sync job not found: {sync_id}"
        )

    job = _sync_jobs[sync_id]

    # Determine type based on status
    if job["status"] == "running":
        job_type = "start"
        message = f"{job['source'].upper()} sync in progress"
    elif job["status"] == "completed":
        job_type = "complete"
        result = job.get("result", {})
        message = (
            f"Completed: {result.get('files_processed', 0)} processed, "
            f"{result.get('files_added', 0)} new, "
            f"{result.get('files_updated', 0)} updated"
        )
    else:
        job_type = "error"
        message = job.get("error", "Unknown error")

    return SyncLogEntryResponse(
        id=job["id"],
        timestamp=job["started_at"],
        source=job["source"],
        type=job_type,
        message=message,
        details=job.get("result"),
    )


@router.get("/history", response_model=SyncHistoryResponse)
def get_sync_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SyncHistoryResponse:
    """
    Get sync job history with pagination.

    Returns most recent sync jobs first.
    """
    # Convert jobs to list and sort by timestamp (most recent first)
    jobs_list = list(_sync_jobs.values())
    jobs_list.sort(key=lambda x: x.get("started_at", ""), reverse=True)

    # Calculate pagination
    total = len(jobs_list)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    # Get page items
    page_items = jobs_list[start_idx:end_idx]

    # Convert to response format
    items = []
    for job in page_items:
        if job["status"] == "running":
            job_type = "start"
            message = f"{job['source'].upper()} sync in progress"
        elif job["status"] == "completed":
            job_type = "complete"
            result = job.get("result", {})
            message = (
                f"Completed: {result.get('files_processed', 0)} processed, "
                f"{result.get('files_added', 0)} new"
            )
        else:
            job_type = "error"
            message = job.get("error", "Unknown error")

        items.append(SyncLogEntryResponse(
            id=job["id"],
            timestamp=job["started_at"],
            source=job["source"],
            type=job_type,
            message=message,
            details=job.get("result"),
        ))

    return SyncHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ============== Sync Inspection APIs (Issue #23) ==============
# APIs for inspecting synchronized data: folder tree, sheets preview, scheduler status

class TreeNode(BaseModel):
    """폴더/파일 트리 노드"""
    name: str
    type: str  # 'folder' or 'file'
    path: Optional[str] = None
    children: Optional[List["TreeNode"]] = None
    metadata: Optional[Dict[str, Any]] = None


class FolderTreeResponse(BaseModel):
    """폴더 트리 응답"""
    projects: List[TreeNode]
    total_files: int
    total_folders: int
    generated_at: str


class SheetInfo(BaseModel):
    """개별 시트 정보"""
    sheet_id: str
    sheet_name: str
    source_type: str
    row_count: int
    last_synced_at: Optional[str] = None
    last_row_synced: int
    sample_data: List[Dict[str, Any]] = []


class SheetPreviewResponse(BaseModel):
    """시트 미리보기 응답"""
    sheets: Dict[str, SheetInfo]
    total_synced_rows: int


class ScheduledJobInfo(BaseModel):
    """스케줄된 작업 정보"""
    job_id: str
    name: str
    cron_expression: str
    next_run_time: Optional[str] = None
    last_run_time: Optional[str] = None
    last_status: Optional[str] = None
    enabled: bool


class SchedulerStatusResponse(BaseModel):
    """스케줄러 상태 응답"""
    is_running: bool
    apscheduler_available: bool
    jobs: List[ScheduledJobInfo]
    next_nas_sync: Optional[str] = None
    next_sheets_sync: Optional[str] = None


def _build_folder_tree(
    db: Session,
    project_code: Optional[str] = None,
    max_depth: int = 5
) -> Dict[str, Any]:
    """
    VideoFile.file_path에서 폴더 트리 구조 생성.

    Args:
        db: Database session
        project_code: Optional filter by project
        max_depth: Maximum tree depth

    Returns:
        Tree structure with files and folders
    """
    from src.models.video_file import VideoFile
    from sqlalchemy import select

    # Query all file paths
    query = select(VideoFile.file_path, VideoFile.file_name, VideoFile.file_size_bytes,
                   VideoFile.version_type, VideoFile.display_title).where(
        VideoFile.deleted_at.is_(None),
        VideoFile.is_hidden == False
    )

    if project_code:
        query = query.where(VideoFile.file_path.ilike(f'%{project_code}%'))

    files = db.execute(query).all()

    # Build tree structure
    tree: Dict[str, Any] = {}
    total_files = 0
    folder_set = set()

    for file_path, file_name, file_size, version_type, display_title in files:
        # Normalize path separators
        normalized_path = file_path.replace('\\', '/')

        # Split path into parts
        parts = normalized_path.split('/')

        # Skip if too deep
        relevant_parts = parts[:-1]  # Exclude filename
        if len(relevant_parts) > max_depth:
            relevant_parts = relevant_parts[:max_depth]

        # Build tree
        current = tree
        for i, part in enumerate(relevant_parts):
            if not part:
                continue
            folder_set.add('/'.join(relevant_parts[:i+1]))
            if part not in current:
                current[part] = {'_children': {}, '_files': []}
            current = current[part]['_children']

        # Add file to the deepest folder
        if parts:
            folder_path = '/'.join(parts[:-1])
            file_node = {
                'name': file_name,
                'path': file_path,
                'size_bytes': file_size,
                'version_type': version_type,
                'display_title': display_title,
            }

            # Find or create the folder in tree
            parent = tree
            for part in relevant_parts:
                if not part:
                    continue
                if part in parent:
                    parent = parent[part]['_children']
                else:
                    break
            else:
                # Add file to last valid folder
                if relevant_parts:
                    last_part = relevant_parts[-1]
                    # Navigate back to add file
                    nav = tree
                    for p in relevant_parts[:-1]:
                        if p and p in nav:
                            nav = nav[p]['_children']
                    if last_part in nav:
                        nav[last_part]['_files'].append(file_node)

        total_files += 1

    def dict_to_tree_nodes(d: Dict, depth: int = 0) -> List[TreeNode]:
        """Convert dict structure to TreeNode list"""
        nodes = []
        for name, content in d.items():
            if name.startswith('_'):
                continue

            children_nodes = []
            if depth < max_depth and '_children' in content:
                children_nodes = dict_to_tree_nodes(content['_children'], depth + 1)

            # Add file nodes
            if '_files' in content:
                for f in content['_files'][:50]:  # Limit files per folder
                    children_nodes.append(TreeNode(
                        name=f['name'],
                        type='file',
                        path=f['path'],
                        metadata={
                            'size_bytes': f['size_bytes'],
                            'version_type': f['version_type'],
                            'display_title': f['display_title'],
                        }
                    ))

            nodes.append(TreeNode(
                name=name,
                type='folder',
                children=children_nodes if children_nodes else None,
                metadata={'file_count': len(content.get('_files', []))}
            ))

        return nodes

    project_nodes = dict_to_tree_nodes(tree)

    return {
        'projects': project_nodes,
        'total_files': total_files,
        'total_folders': len(folder_set),
        'generated_at': datetime.utcnow().isoformat(),
    }


@router.get("/tree", response_model=FolderTreeResponse)
def get_folder_tree(
    project_code: Optional[str] = Query(None, description="필터링할 프로젝트 코드"),
    max_depth: int = Query(5, ge=1, le=10, description="최대 트리 깊이"),
    db: Session = Depends(get_db),
) -> FolderTreeResponse:
    """
    동기화된 NAS 폴더 구조를 트리 형태로 반환.

    VideoFile 테이블의 file_path를 분석하여 폴더 구조를 생성합니다.
    프로젝트 코드로 필터링하거나 트리 깊이를 제한할 수 있습니다.

    **project_code**: WSOP, GGMILLIONS, MPP, PAD, GOG, HCL
    """
    tree_data = _build_folder_tree(db, project_code, max_depth)
    return FolderTreeResponse(**tree_data)


@router.get("/sheets/preview", response_model=SheetPreviewResponse)
def get_sheets_preview(
    limit: int = Query(5, ge=1, le=20, description="미리보기 행 수"),
    db: Session = Depends(get_db),
) -> SheetPreviewResponse:
    """
    동기화된 Google Sheets 데이터 미리보기.

    각 시트의 상태와 최근 동기화된 데이터 샘플을 반환합니다.
    hand_clips 테이블에서 데이터를 조회합니다.
    """
    from sqlalchemy import text

    sheets = {}
    total_rows = 0

    # Get configured sheets info
    sheet_configs = {
        'hand_analysis': {
            'sheet_id': '1ABC...XYZ',
            'sheet_name': 'Hand Analysis',
            'source_type': 'hand_analysis',
        },
        'hand_database': {
            'sheet_id': '1DEF...UVW',
            'sheet_name': 'Hand Database',
            'source_type': 'hand_database',
        },
    }

    for key, config in sheet_configs.items():
        # Get sync state
        sync_state = db.execute(
            text("""
                SELECT last_row_synced, last_synced_at
                FROM pokervod.google_sheet_sync
                WHERE sheet_id = :sheet_id
            """),
            {'sheet_id': config['sheet_id']}
        ).first()

        last_row = sync_state[0] if sync_state else 0
        last_synced = sync_state[1].isoformat() if sync_state and sync_state[1] else None

        # Get row count from hand_clips
        row_count_result = db.execute(
            text("""
                SELECT COUNT(*) FROM pokervod.hand_clips
                WHERE sheet_source = :source
            """),
            {'source': config['source_type']}
        ).scalar() or 0

        # Get sample data
        sample_rows = db.execute(
            text("""
                SELECT id, title, timecode, notes, hand_grade, created_at
                FROM pokervod.hand_clips
                WHERE sheet_source = :source
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {'source': config['source_type'], 'limit': limit}
        ).all()

        sample_data = [
            {
                'id': str(row[0]),
                'title': row[1],
                'timecode': row[2],
                'notes': row[3],
                'hand_grade': row[4],
                'created_at': row[5].isoformat() if row[5] else None,
            }
            for row in sample_rows
        ]

        sheets[key] = SheetInfo(
            sheet_id=config['sheet_id'],
            sheet_name=config['sheet_name'],
            source_type=config['source_type'],
            row_count=row_count_result,
            last_synced_at=last_synced,
            last_row_synced=last_row,
            sample_data=sample_data,
        )

        total_rows += row_count_result

    return SheetPreviewResponse(
        sheets=sheets,
        total_synced_rows=total_rows,
    )


@router.get("/scheduler", response_model=SchedulerStatusResponse)
def get_scheduler_status_for_sync() -> SchedulerStatusResponse:
    """
    동기화 관련 스케줄러 상태 조회.

    APScheduler의 실행 상태와 등록된 동기화 작업 목록을 반환합니다.
    nas_scan, sheet_sync 작업의 다음 실행 시간을 확인할 수 있습니다.
    """
    from src.services.scheduler_service import get_scheduler

    scheduler = get_scheduler()
    status = scheduler.get_status()
    schedules = scheduler.get_schedules()

    # Convert jobs to response format
    jobs = []
    next_nas_sync = None
    next_sheets_sync = None

    # Get job info from status
    for job_info in status.get('jobs', []):
        job_id = job_info['id']
        schedule_config = schedules.get(job_id, {})

        job = ScheduledJobInfo(
            job_id=job_id,
            name=job_info.get('name', job_id),
            cron_expression=schedule_config.get('cron', ''),
            next_run_time=job_info.get('next_run'),
            last_run_time=status.get('history', {}).get(job_id, {}).get('started_at'),
            last_status=status.get('history', {}).get(job_id, {}).get('status'),
            enabled=schedule_config.get('enabled', True),
        )
        jobs.append(job)

        # Track next sync times
        if job_id == 'nas_scan' and job_info.get('next_run'):
            next_nas_sync = job_info['next_run']
        elif job_id == 'sheet_sync' and job_info.get('next_run'):
            next_sheets_sync = job_info['next_run']

    # If scheduler not running, show default schedules
    if not jobs:
        for job_id, config in schedules.items():
            if job_id in ['nas_scan', 'sheet_sync', 'daily_validation']:
                jobs.append(ScheduledJobInfo(
                    job_id=job_id,
                    name=config['name'],
                    cron_expression=config['cron'],
                    enabled=config['enabled'],
                ))

    return SchedulerStatusResponse(
        is_running=status.get('running', False),
        apscheduler_available=status.get('available', False),
        jobs=jobs,
        next_nas_sync=next_nas_sync,
        next_sheets_sync=next_sheets_sync,
    )
