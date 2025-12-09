/**
 * CatalogGrid - 카탈로그 그리드 컴포넌트
 * BLOCK_FRONTEND / FrontendAgent
 */

import type { CatalogItem } from '../../types/catalog';
import { CatalogCard } from './CatalogCard';

interface CatalogGridProps {
  items: CatalogItem[];
  onItemClick?: (item: CatalogItem) => void;
  isLoading?: boolean;
}

/**
 * 로딩 스켈레톤
 */
function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="aspect-video bg-gray-700 rounded-t-lg" />
      <div className="p-3 bg-gray-800 rounded-b-lg">
        <div className="h-4 bg-gray-700 rounded w-3/4 mb-2" />
        <div className="h-3 bg-gray-700 rounded w-1/2" />
      </div>
    </div>
  );
}

export function CatalogGrid({ items, onItemClick, isLoading = false }: CatalogGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {Array.from({ length: 10 }).map((_, i) => (
          <LoadingSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-400">
        <svg
          className="w-16 h-16 mb-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"
          />
        </svg>
        <p className="text-lg font-medium">검색 결과가 없습니다</p>
        <p className="text-sm mt-1">필터 조건을 변경해 보세요</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
      {items.map((item) => (
        <CatalogCard key={item.id} item={item} onClick={onItemClick} />
      ))}
    </div>
  );
}

export default CatalogGrid;
