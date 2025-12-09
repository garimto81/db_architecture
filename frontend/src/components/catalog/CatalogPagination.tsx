/**
 * CatalogPagination - 페이지네이션 컴포넌트
 * BLOCK_FRONTEND / FrontendAgent
 */


interface CatalogPaginationProps {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  isLoading?: boolean;
}

export function CatalogPagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
  isLoading = false,
}: CatalogPaginationProps) {
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  // 표시할 페이지 번호 계산
  const getPageNumbers = () => {
    const pages: (number | 'ellipsis')[] = [];
    const maxVisible = 7;

    if (totalPages <= maxVisible) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }

    // 항상 첫 페이지
    pages.push(1);

    if (page > 3) {
      pages.push('ellipsis');
    }

    // 현재 페이지 주변
    const start = Math.max(2, page - 1);
    const end = Math.min(totalPages - 1, page + 1);

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (page < totalPages - 2) {
      pages.push('ellipsis');
    }

    // 항상 마지막 페이지
    if (totalPages > 1) {
      pages.push(totalPages);
    }

    return pages;
  };

  if (totalPages <= 1) {
    return (
      <div className="text-center text-gray-400 text-sm py-4">
        총 {total.toLocaleString()}개 항목
      </div>
    );
  }

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-6 py-4">
      {/* 결과 정보 */}
      <p className="text-sm text-gray-400">
        {total.toLocaleString()}개 중 {startItem.toLocaleString()}-{endItem.toLocaleString()}
      </p>

      {/* 페이지 네비게이션 */}
      <div className="flex items-center gap-1">
        {/* 이전 버튼 */}
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1 || isLoading}
          className="px-2 py-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        {/* 페이지 번호 */}
        {getPageNumbers().map((pageNum, idx) =>
          pageNum === 'ellipsis' ? (
            <span key={`ellipsis-${idx}`} className="px-2 text-gray-500">
              ...
            </span>
          ) : (
            <button
              key={pageNum}
              onClick={() => onPageChange(pageNum)}
              disabled={isLoading}
              className={`
                px-3 py-1.5 text-sm rounded transition-colors
                ${
                  pageNum === page
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:bg-gray-700 hover:text-white'
                }
                disabled:opacity-50
              `}
            >
              {pageNum}
            </button>
          )
        )}

        {/* 다음 버튼 */}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages || isLoading}
          className="px-2 py-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* 페이지당 항목 수 (옵션) */}
      <div className="hidden sm:block text-sm text-gray-500">
        {totalPages} 페이지
      </div>
    </div>
  );
}

export default CatalogPagination;
