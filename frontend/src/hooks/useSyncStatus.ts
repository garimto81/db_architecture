/**
 * Sync Status Hook - TanStack Query 기반 동기화 상태 관리
 * BLOCK_FRONTEND / FrontendAgent
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchSyncStatus, fetchSyncHistory, triggerSync } from '../services';
import { useSyncStore } from '../store';
import type { SyncSource, SyncLogEntry, PaginatedResponse } from '../types';

// 쿼리 키
export const SYNC_QUERY_KEYS = {
  status: ['sync', 'status'] as const,
  history: (page: number) => ['sync', 'history', page] as const,
};

/**
 * 동기화 상태 조회 훅
 */
export function useSyncStatus() {
  return useQuery({
    queryKey: SYNC_QUERY_KEYS.status,
    queryFn: fetchSyncStatus,
    refetchInterval: 30000, // 30초마다 폴링 (WebSocket 백업)
    staleTime: 10000, // 10초간 캐시 유지
  });
}

/**
 * 동기화 히스토리 조회 훅
 */
export function useSyncHistory(page = 1) {
  return useQuery<PaginatedResponse<SyncLogEntry>>({
    queryKey: SYNC_QUERY_KEYS.history(page),
    queryFn: () => fetchSyncHistory(page),
    staleTime: 60000, // 1분간 캐시 유지
  });
}

/**
 * 수동 동기화 트리거 훅
 */
export function useTriggerSync() {
  const queryClient = useQueryClient();
  const { startSync, addNotification } = useSyncStore();

  return useMutation({
    mutationFn: (source: SyncSource) => triggerSync(source),
    onMutate: (source) => {
      // Optimistic update
      startSync(source);
      addNotification({
        type: 'info',
        title: '동기화 시작',
        message: `${source.toUpperCase()} 동기화를 시작합니다...`,
      });
    },
    onSuccess: () => {
      // 상태 새로고침
      queryClient.invalidateQueries({ queryKey: SYNC_QUERY_KEYS.status });
    },
    onError: (error, source) => {
      console.error(`Failed to trigger ${source} sync:`, error);
      addNotification({
        type: 'error',
        title: '동기화 실패',
        message: `${source.toUpperCase()} 동기화 요청에 실패했습니다.`,
      });
    },
  });
}
