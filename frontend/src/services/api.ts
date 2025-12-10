/**
 * API Client - Axios 인스턴스 설정
 * BLOCK_FRONTEND / FrontendAgent
 */

import axios from 'axios';

// 환경 변수에서 API URL 가져오기
// Production: 상대 경로 사용 (Nginx 프록시)
// Development: VITE_API_BASE_URL 환경변수 또는 localhost:9000
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// Axios 인스턴스 생성
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 요청 인터셉터
apiClient.interceptors.request.use(
  (config) => {
    // 디버그 모드에서 요청 로깅
    if (import.meta.env.VITE_DEBUG === 'true') {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 응답 인터셉터
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // 에러 응답 처리
    if (error.response) {
      console.error(`[API Error] ${error.response.status}: ${error.response.data?.detail || error.message}`);
    } else if (error.request) {
      console.error('[API Error] No response received');
    } else {
      console.error('[API Error]', error.message);
    }
    return Promise.reject(error);
  }
);

// WebSocket URL 가져오기
// Production: 현재 호스트 기반 ws:// 또는 wss:// 사용
// Development: VITE_WS_BASE_URL 환경변수 사용
export const getWsUrl = (path: string): string => {
  if (import.meta.env.VITE_WS_BASE_URL) {
    return `${import.meta.env.VITE_WS_BASE_URL}${path}`;
  }
  // Production: 현재 호스트 기반 WebSocket URL 생성
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path}`;
};

// ============== Issue #28: Infinite Scroll API Functions ==============

import type { CursorPaginatedResponse, VideoFileResponse, HandClipResponse } from '../types/sync';

/**
 * NAS 비디오 파일 목록 조회 (Cursor 페이지네이션)
 * @param cursor - 다음 페이지 커서 (null = 첫 페이지)
 * @param project - 프로젝트 필터 (선택)
 * @param limit - 페이지당 항목 수 (기본: 20)
 */
export async function fetchVideoFiles(
  cursor: string | null = null,
  project?: string,
  limit: number = 20
): Promise<CursorPaginatedResponse<VideoFileResponse>> {
  const params = new URLSearchParams();
  if (cursor) params.set('cursor', cursor);
  if (project) params.set('project', project);
  params.set('limit', String(limit));

  const response = await apiClient.get<CursorPaginatedResponse<VideoFileResponse>>(
    `/api/sync/files/cursor?${params}`
  );
  return response.data;
}

/**
 * Hand Clips 목록 조회 (Cursor 페이지네이션)
 * @param cursor - 다음 페이지 커서 (null = 첫 페이지)
 * @param source - 시트 소스 필터 (선택)
 * @param limit - 페이지당 항목 수 (기본: 20)
 */
export async function fetchHandClipsCursor(
  cursor: string | null = null,
  source?: string,
  limit: number = 20
): Promise<CursorPaginatedResponse<HandClipResponse>> {
  const params = new URLSearchParams();
  if (cursor) params.set('cursor', cursor);
  if (source) params.set('source', source);
  params.set('limit', String(limit));

  const response = await apiClient.get<CursorPaginatedResponse<HandClipResponse>>(
    `/api/sync/hand-clips/cursor?${params}`
  );
  return response.data;
}

export default apiClient;
