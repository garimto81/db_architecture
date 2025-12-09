/**
 * Dashboard Types - 대시보드 통계 데이터 타입 정의
 * BLOCK_FRONTEND / FrontendAgent
 */

import type { SyncLogEntry } from './sync';

// 저장소 사용량
export interface StorageUsage {
  total_size_gb: number;
  by_project: Record<string, number>;
}

// 프로젝트별 파일 수
export interface ProjectStats {
  code: string;
  name: string;
  files_count: number;
  percentage: number;
}

// REST API: /api/dashboard/stats 응답
export interface DashboardStatsResponse {
  total_files: number;
  total_hand_clips: number;
  total_catalogs: number;
  by_project: Record<string, number>;
  by_year: Record<string, number>;
  recent_syncs: SyncLogEntry[];
  storage_usage: StorageUsage;
}

// 시스템 헬스 상태
export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  database: {
    connected: boolean;
    latency_ms: number;
  };
  nas: {
    accessible: boolean;
    path: string;
  };
  scheduler: {
    running: boolean;
    jobs_count: number;
  };
  timestamp: string;
}

// REST API: /api/dashboard/health 응답
export interface HealthResponse extends HealthStatus {}
