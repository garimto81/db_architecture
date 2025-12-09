/**
 * Sync API - 동기화 관련 API 호출
 * BLOCK_FRONTEND / FrontendAgent
 */

import { apiClient } from './api';
import type { SyncStatusResponse, SyncLogEntry, SyncSource, PaginatedResponse } from '../types';

/**
 * 현재 동기화 상태 조회
 */
export async function fetchSyncStatus(): Promise<SyncStatusResponse> {
  const response = await apiClient.get<SyncStatusResponse>('/api/sync/status');
  return response.data;
}

/**
 * 동기화 히스토리 조회 (페이지네이션)
 */
export async function fetchSyncHistory(
  page = 1,
  pageSize = 20
): Promise<PaginatedResponse<SyncLogEntry>> {
  const response = await apiClient.get<PaginatedResponse<SyncLogEntry>>('/api/sync/history', {
    params: { page, page_size: pageSize },
  });
  return response.data;
}

/**
 * 수동 동기화 트리거
 */
export async function triggerSync(source: SyncSource): Promise<{ sync_id: string }> {
  const response = await apiClient.post<{ sync_id: string }>(`/api/sync/trigger/${source}`);
  return response.data;
}

/**
 * 특정 동기화 작업 상태 조회
 */
export async function fetchSyncJob(syncId: string): Promise<SyncLogEntry> {
  const response = await apiClient.get<SyncLogEntry>(`/api/sync/jobs/${syncId}`);
  return response.data;
}
