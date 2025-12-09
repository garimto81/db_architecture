/**
 * Sync Types - WebSocket 및 REST API 데이터 타입 정의
 * BLOCK_FRONTEND / FrontendAgent
 */

// 동기화 상태
export type SyncStatus = 'idle' | 'running' | 'error';

// 동기화 소스
export type SyncSource = 'nas' | 'sheets';

// 동기화 트리거 유형
export type SyncTrigger = 'scheduler' | 'manual';

// WebSocket 메시지 타입
export type WsMessageType =
  | 'sync_start'
  | 'sync_progress'
  | 'sync_complete'
  | 'sync_error'
  | 'file_found'
  | 'sheet_updated';

// WebSocket 메시지 기본 구조
export interface WsMessage<T = unknown> {
  type: WsMessageType;
  timestamp: string;
  payload: T;
}

// 동기화 시작 페이로드
export interface SyncStartPayload {
  sync_id: string;
  source: SyncSource;
  triggered_by: SyncTrigger;
}

// 동기화 진행 페이로드
export interface SyncProgressPayload {
  sync_id: string;
  source: SyncSource;
  current: number;
  total: number;
  current_file?: string;
  percentage: number;
}

// 동기화 완료 페이로드
export interface SyncCompletePayload {
  sync_id: string;
  source: SyncSource;
  duration_ms: number;
  files_processed: number;
  files_added: number;
  files_updated: number;
  errors: number;
}

// 동기화 에러 페이로드
export interface SyncErrorPayload {
  sync_id: string;
  source: SyncSource;
  error_code: string;
  message: string;
}

// NAS 동기화 상태
export interface NasSyncState {
  last_sync: string | null;
  status: SyncStatus;
  files_count: number;
  next_scheduled: string | null;
}

// Sheets 동기화 상태
export interface SheetsSyncState {
  last_sync: string | null;
  status: SyncStatus;
  rows_count: number;
  next_scheduled: string | null;
}

// 스케줄러 작업
export interface SchedulerJob {
  id: string;
  name: string;
  next_run: string;
  interval_seconds: number;
}

// 스케줄러 상태
export interface SchedulerState {
  is_running: boolean;
  jobs: SchedulerJob[];
}

// REST API: /api/sync/status 응답
export interface SyncStatusResponse {
  nas: NasSyncState;
  sheets: SheetsSyncState;
  scheduler: SchedulerState;
}

// 동기화 로그 엔트리
export interface SyncLogEntry {
  id: string;
  timestamp: string;
  source: SyncSource;
  type: 'start' | 'complete' | 'error';
  message: string;
  details?: Record<string, unknown>;
}

// ============== Issue #23: Sync Inspection Types ==============

// 폴더 트리 노드
export interface FolderNode {
  name: string;
  type: 'folder' | 'file';
  path?: string;
  children?: FolderNode[];
  metadata?: {
    file_count?: number;
    size_bytes?: number;
    version_type?: string;
    display_title?: string;
  };
}

// 폴더 트리 응답
export interface FolderTreeResponse {
  projects: FolderNode[];
  total_files: number;
  total_folders: number;
  generated_at: string;
}

// 시트 정보
export interface SheetInfo {
  sheet_id: string;
  sheet_name: string;
  source_type: string;
  row_count: number;
  last_synced_at: string | null;
  last_row_synced: number;
  sample_data: Array<{
    id: string;
    title: string;
    timecode: string;
    notes: string;
    hand_grade: string;
    created_at: string;
  }>;
}

// 시트 미리보기 응답
export interface SheetPreviewResponse {
  sheets: Record<string, SheetInfo>;
  total_synced_rows: number;
}

// 스케줄러 작업 상세
export interface ScheduledJobInfo {
  job_id: string;
  name: string;
  cron_expression: string;
  next_run_time: string | null;
  last_run_time: string | null;
  last_status: string | null;
  enabled: boolean;
}

// 스케줄러 상태 응답
export interface SchedulerStatusResponse {
  is_running: boolean;
  apscheduler_available: boolean;
  jobs: ScheduledJobInfo[];
  next_nas_sync: string | null;
  next_sheets_sync: string | null;
}
