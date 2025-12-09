/**
 * Catalog Types - 카탈로그 관련 타입 정의
 * BLOCK_FRONTEND / FrontendAgent
 */

// 카탈로그 아이템 (비디오 파일)
export interface CatalogItem {
  id: string;
  display_title: string | null;
  file_name: string;
  file_path: string;

  // 기술 메타데이터
  duration_seconds: number | null;
  file_size_bytes: number | null;
  file_format: string | null;
  resolution: string | null;
  version_type: string | null;

  // 컨텍스트
  project_code: string | null;
  project_name: string | null;
  year: number | null;
  event_name: string | null;
  episode_title: string | null;

  // 상태
  is_hidden: boolean;
  hidden_reason: string | null;
  scan_status: string;

  // 타임스탬프
  created_at: string;
  updated_at: string;
  file_mtime: string | null;
}

// 카탈로그 목록 응답
export interface CatalogListResponse {
  items: CatalogItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// 카탈로그 통계
export interface CatalogStats {
  total_files: number;
  visible_files: number;
  hidden_files: number;
  by_project: Record<string, number>;
  by_year: Record<string, number>;
  by_format: Record<string, number>;
  total_duration_hours: number | null;
  total_size_gb: number | null;
}

// 필터 옵션
export interface CatalogFilterOptions {
  projects: Array<{ code: string; name: string; count: number }>;
  years: number[];
  formats: string[];
  version_types: string[];
}

// 필터 파라미터
export interface CatalogFilterParams {
  page?: number;
  page_size?: number;
  project_code?: string;
  year?: number;
  search?: string;
  include_hidden?: boolean;
  version_type?: string;
  file_format?: string;
}

// 프로젝트 코드별 색상
export const PROJECT_COLORS: Record<string, string> = {
  WSOP: 'bg-yellow-500',
  HCL: 'bg-red-500',
  GGMILLIONS: 'bg-blue-500',
  GOG: 'bg-purple-500',
  PAD: 'bg-green-500',
  MPP: 'bg-orange-500',
  OTHER: 'bg-gray-500',
};

// 포맷별 아이콘/스타일
export const FORMAT_LABELS: Record<string, string> = {
  mp4: 'MP4',
  mov: 'MOV',
  mxf: 'MXF',
  avi: 'AVI',
  mkv: 'MKV',
};
