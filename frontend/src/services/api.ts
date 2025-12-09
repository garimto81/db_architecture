/**
 * API Client - Axios 인스턴스 설정
 * BLOCK_FRONTEND / FrontendAgent
 */

import axios from 'axios';

// 환경 변수에서 API URL 가져오기
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
export const getWsUrl = (path: string): string => {
  const wsBaseUrl = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';
  return `${wsBaseUrl}${path}`;
};

export default apiClient;
