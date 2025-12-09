/**
 * Catalog API Service - 카탈로그 API 호출
 * BLOCK_FRONTEND / FrontendAgent
 */

import { apiClient } from './api';
import type {
  CatalogListResponse,
  CatalogStats,
  CatalogFilterOptions,
  CatalogFilterParams,
  CatalogItem,
} from '../types/catalog';

/**
 * 카탈로그 목록 조회
 */
export async function getCatalogItems(
  params: CatalogFilterParams = {}
): Promise<CatalogListResponse> {
  const searchParams = new URLSearchParams();

  if (params.page) searchParams.set('page', params.page.toString());
  if (params.page_size) searchParams.set('page_size', params.page_size.toString());
  if (params.project_code) searchParams.set('project_code', params.project_code);
  if (params.year) searchParams.set('year', params.year.toString());
  if (params.search) searchParams.set('search', params.search);
  if (params.include_hidden) searchParams.set('include_hidden', 'true');
  if (params.version_type) searchParams.set('version_type', params.version_type);
  if (params.file_format) searchParams.set('file_format', params.file_format);

  const queryString = searchParams.toString();
  const url = queryString ? `/api/catalog?${queryString}` : '/api/catalog';

  const response = await apiClient.get<CatalogListResponse>(url);
  return response.data;
}

/**
 * 카탈로그 통계 조회
 */
export async function getCatalogStats(
  includeHidden: boolean = false
): Promise<CatalogStats> {
  const url = includeHidden
    ? '/api/catalog/stats?include_hidden=true'
    : '/api/catalog/stats';

  const response = await apiClient.get<CatalogStats>(url);
  return response.data;
}

/**
 * 필터 옵션 조회
 */
export async function getCatalogFilterOptions(): Promise<CatalogFilterOptions> {
  const response = await apiClient.get<CatalogFilterOptions>('/api/catalog/filters');
  return response.data;
}

/**
 * 개별 카탈로그 아이템 조회
 */
export async function getCatalogItem(videoId: string): Promise<CatalogItem> {
  const response = await apiClient.get<CatalogItem>(`/api/catalog/${videoId}`);
  return response.data;
}
