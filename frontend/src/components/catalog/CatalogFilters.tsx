/**
 * CatalogFilters - 카탈로그 필터 컴포넌트
 * BLOCK_FRONTEND / FrontendAgent
 */

import { useState, useEffect } from 'react';
import type { CatalogFilterOptions, CatalogFilterParams } from '../../types/catalog';
import { SearchInput, Select } from '../common';

interface CatalogFiltersProps {
  filters: CatalogFilterParams;
  filterOptions: CatalogFilterOptions | null;
  onFilterChange: (filters: CatalogFilterParams) => void;
  isLoading?: boolean;
}

export function CatalogFilters({
  filters,
  filterOptions,
  onFilterChange,
  isLoading = false,
}: CatalogFiltersProps) {
  const [searchValue, setSearchValue] = useState(filters.search || '');

  // 검색어 디바운싱
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchValue !== filters.search) {
        onFilterChange({ ...filters, search: searchValue || undefined, page: 1 });
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchValue]);

  const handleProjectChange = (value: string) => {
    onFilterChange({
      ...filters,
      project_code: value || undefined,
      page: 1,
    });
  };

  const handleYearChange = (value: string) => {
    onFilterChange({
      ...filters,
      year: value ? parseInt(value, 10) : undefined,
      page: 1,
    });
  };

  const handleFormatChange = (value: string) => {
    onFilterChange({
      ...filters,
      file_format: value || undefined,
      page: 1,
    });
  };

  const handleVersionTypeChange = (value: string) => {
    onFilterChange({
      ...filters,
      version_type: value || undefined,
      page: 1,
    });
  };

  const handleClearFilters = () => {
    setSearchValue('');
    onFilterChange({ page: 1, page_size: filters.page_size });
  };

  const hasActiveFilters =
    filters.project_code ||
    filters.year ||
    filters.search ||
    filters.file_format ||
    filters.version_type;

  // 프로젝트 옵션
  const projectOptions = [
    { value: '', label: '전체 프로젝트' },
    ...(filterOptions?.projects || []).map((p) => ({
      value: p.code,
      label: `${p.name} (${p.count})`,
    })),
  ];

  // 연도 옵션
  const yearOptions = [
    { value: '', label: '전체 연도' },
    ...(filterOptions?.years || []).map((y) => ({
      value: y.toString(),
      label: y.toString(),
    })),
  ];

  // 포맷 옵션
  const formatOptions = [
    { value: '', label: '전체 포맷' },
    ...(filterOptions?.formats || []).map((f) => ({
      value: f,
      label: f.toUpperCase(),
    })),
  ];

  // 버전 타입 옵션
  const versionOptions = [
    { value: '', label: '전체 버전' },
    ...(filterOptions?.version_types || []).map((v) => ({
      value: v,
      label: v,
    })),
  ];

  return (
    <div className="bg-gray-800 rounded-lg p-4 mb-6">
      <div className="flex flex-col gap-4">
        {/* 검색 */}
        <div className="flex-1">
          <SearchInput
            value={searchValue}
            onChange={setSearchValue}
            placeholder="제목, 파일명으로 검색..."
            className="w-full"
          />
        </div>

        {/* 필터 행 */}
        <div className="flex flex-wrap gap-3">
          <Select
            value={filters.project_code || ''}
            onChange={handleProjectChange}
            options={projectOptions}
            className="w-40"
            disabled={isLoading}
          />

          <Select
            value={filters.year?.toString() || ''}
            onChange={handleYearChange}
            options={yearOptions}
            className="w-32"
            disabled={isLoading}
          />

          <Select
            value={filters.file_format || ''}
            onChange={handleFormatChange}
            options={formatOptions}
            className="w-32"
            disabled={isLoading}
          />

          <Select
            value={filters.version_type || ''}
            onChange={handleVersionTypeChange}
            options={versionOptions}
            className="w-36"
            disabled={isLoading}
          />

          {hasActiveFilters && (
            <button
              onClick={handleClearFilters}
              className="px-3 py-2 text-sm text-gray-400 hover:text-white transition-colors"
            >
              필터 초기화
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default CatalogFilters;
