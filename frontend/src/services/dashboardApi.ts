/**
 * Dashboard API - 대시보드 관련 API 호출
 * BLOCK_FRONTEND / FrontendAgent
 */

import { apiClient } from './api';
import type { DashboardStatsResponse, HealthResponse } from '../types';

/**
 * 대시보드 통계 조회
 */
export async function fetchDashboardStats(): Promise<DashboardStatsResponse> {
  const response = await apiClient.get<DashboardStatsResponse>('/api/dashboard/stats');
  return response.data;
}

/**
 * 시스템 헬스체크
 */
export async function fetchSystemHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>('/api/dashboard/health');
  return response.data;
}
