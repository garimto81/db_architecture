/**
 * Dashboard Stats Hook - TanStack Query 기반 대시보드 통계 관리
 * BLOCK_FRONTEND / FrontendAgent
 */

import { useQuery } from '@tanstack/react-query';
import { fetchDashboardStats, fetchSystemHealth } from '../services';

// 쿼리 키
export const DASHBOARD_QUERY_KEYS = {
  stats: ['dashboard', 'stats'] as const,
  health: ['dashboard', 'health'] as const,
};

/**
 * 대시보드 통계 조회 훅
 */
export function useDashboardStats() {
  return useQuery({
    queryKey: DASHBOARD_QUERY_KEYS.stats,
    queryFn: fetchDashboardStats,
    staleTime: 60000, // 1분간 캐시 유지
    refetchInterval: 120000, // 2분마다 새로고침
  });
}

/**
 * 시스템 헬스 조회 훅
 */
export function useSystemHealth() {
  return useQuery({
    queryKey: DASHBOARD_QUERY_KEYS.health,
    queryFn: fetchSystemHealth,
    staleTime: 30000, // 30초간 캐시 유지
    refetchInterval: 60000, // 1분마다 새로고침
  });
}
