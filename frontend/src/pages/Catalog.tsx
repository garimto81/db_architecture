/**
 * Catalog Page - Netflix 스타일 비디오 카탈로그
 * BLOCK_FRONTEND / FrontendAgent
 */

import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getCatalogItems,
  getCatalogStats,
  getCatalogFilterOptions,
} from '../services/catalogApi';
import type { CatalogFilterParams, CatalogItem } from '../types/catalog';
import {
  CatalogGrid,
  CatalogFilters,
  CatalogStats,
  CatalogPagination,
} from '../components/catalog';
import { Card } from '../components/common';

const DEFAULT_PAGE_SIZE = 20;

export function Catalog() {
  // 필터 상태
  const [filters, setFilters] = useState<CatalogFilterParams>({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
  });

  // 선택된 아이템 (상세 보기용)
  const [selectedItem, setSelectedItem] = useState<CatalogItem | null>(null);

  // 카탈로그 데이터 조회
  const {
    data: catalogData,
    isLoading: isCatalogLoading,
    error: catalogError,
  } = useQuery({
    queryKey: ['catalog', filters],
    queryFn: () => getCatalogItems(filters),
  });

  // 통계 조회
  const { data: stats, isLoading: isStatsLoading } = useQuery({
    queryKey: ['catalogStats'],
    queryFn: () => getCatalogStats(false),
    staleTime: 60000, // 1분간 캐시
  });

  // 필터 옵션 조회
  const { data: filterOptions } = useQuery({
    queryKey: ['catalogFilterOptions'],
    queryFn: getCatalogFilterOptions,
    staleTime: 300000, // 5분간 캐시
  });

  // 필터 변경 핸들러
  const handleFilterChange = useCallback((newFilters: CatalogFilterParams) => {
    setFilters(newFilters);
  }, []);

  // 페이지 변경 핸들러
  const handlePageChange = useCallback(
    (page: number) => {
      setFilters((prev) => ({ ...prev, page }));
      // 스크롤 상단으로
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    []
  );

  // 아이템 클릭 핸들러
  const handleItemClick = useCallback((item: CatalogItem) => {
    setSelectedItem(item);
    // TODO: 모달 또는 상세 페이지로 이동
    console.log('Selected item:', item);
  }, []);

  // 에러 상태
  if (catalogError) {
    return (
      <div className="p-6">
        <Card className="p-8 text-center">
          <div className="text-red-400 mb-4">
            <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">데이터를 불러올 수 없습니다</h2>
          <p className="text-gray-400">
            {catalogError instanceof Error ? catalogError.message : '알 수 없는 오류가 발생했습니다'}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            새로고침
          </button>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* 헤더 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Video Catalog</h1>
        <p className="text-gray-400 mt-1">
          NAS에서 동기화된 비디오 파일을 탐색합니다
        </p>
      </div>

      {/* 통계 */}
      <CatalogStats stats={stats || null} isLoading={isStatsLoading} />

      {/* 필터 */}
      <CatalogFilters
        filters={filters}
        filterOptions={filterOptions || null}
        onFilterChange={handleFilterChange}
        isLoading={isCatalogLoading}
      />

      {/* 그리드 */}
      <CatalogGrid
        items={catalogData?.items || []}
        onItemClick={handleItemClick}
        isLoading={isCatalogLoading}
      />

      {/* 페이지네이션 */}
      {catalogData && (
        <CatalogPagination
          page={catalogData.page}
          totalPages={catalogData.total_pages}
          total={catalogData.total}
          pageSize={catalogData.page_size}
          onPageChange={handlePageChange}
          isLoading={isCatalogLoading}
        />
      )}

      {/* 선택된 아이템 정보 (디버그용 - 나중에 모달로 변경) */}
      {selectedItem && (
        <div className="fixed bottom-4 right-4 max-w-md bg-gray-800 rounded-lg shadow-xl p-4 border border-gray-700">
          <div className="flex justify-between items-start mb-2">
            <h3 className="font-medium text-white truncate pr-4">
              {selectedItem.display_title || selectedItem.file_name}
            </h3>
            <button
              onClick={() => setSelectedItem(null)}
              className="text-gray-400 hover:text-white"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <p className="text-sm text-gray-400 truncate mb-2">{selectedItem.file_path}</p>
          <div className="flex gap-2 text-xs">
            {selectedItem.project_code && (
              <span className="px-2 py-1 bg-blue-600 rounded">{selectedItem.project_code}</span>
            )}
            {selectedItem.year && (
              <span className="px-2 py-1 bg-gray-700 rounded">{selectedItem.year}</span>
            )}
            {selectedItem.file_format && (
              <span className="px-2 py-1 bg-gray-700 rounded">{selectedItem.file_format.toUpperCase()}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default Catalog;
