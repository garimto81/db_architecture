/**
 * Dashboard Store - Zustand 기반 대시보드 상태 관리
 * BLOCK_FRONTEND / FrontendAgent
 */

import { create } from 'zustand';
import type { DashboardStatsResponse, HealthStatus } from '../types';

interface DashboardState {
  // 통계 데이터
  stats: DashboardStatsResponse | null;
  isStatsLoading: boolean;
  statsError: string | null;

  // 시스템 헬스
  health: HealthStatus | null;
  isHealthLoading: boolean;
  healthError: string | null;

  // 액션: 통계
  setStats: (stats: DashboardStatsResponse) => void;
  setStatsLoading: (loading: boolean) => void;
  setStatsError: (error: string | null) => void;

  // 액션: 헬스
  setHealth: (health: HealthStatus) => void;
  setHealthLoading: (loading: boolean) => void;
  setHealthError: (error: string | null) => void;

  // 액션: 초기화
  reset: () => void;
}

const initialState = {
  stats: null,
  isStatsLoading: false,
  statsError: null,
  health: null,
  isHealthLoading: false,
  healthError: null,
};

export const useDashboardStore = create<DashboardState>((set) => ({
  ...initialState,

  // 통계 액션
  setStats: (stats) => set({ stats, statsError: null }),
  setStatsLoading: (loading) => set({ isStatsLoading: loading }),
  setStatsError: (error) => set({ statsError: error, isStatsLoading: false }),

  // 헬스 액션
  setHealth: (health) => set({ health, healthError: null }),
  setHealthLoading: (loading) => set({ isHealthLoading: loading }),
  setHealthError: (error) => set({ healthError: error, isHealthLoading: false }),

  // 초기화
  reset: () => set(initialState),
}));
