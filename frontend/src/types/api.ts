/**
 * API Types - 공통 API 타입 정의
 * BLOCK_FRONTEND / FrontendAgent
 */

// API 에러 응답
export interface ApiError {
  detail: string;
  status_code: number;
}

// 페이지네이션 요청 파라미터
export interface PaginationParams {
  page?: number;
  page_size?: number;
}

// 페이지네이션 응답
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// API 응답 래퍼
export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}
