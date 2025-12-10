/**
 * InfiniteScrollList - 무한 스크롤 공통 컴포넌트
 * BLOCK_FRONTEND / FrontendAgent
 * Issue #28: Cursor-based Pagination
 *
 * 특징:
 * - TanStack Query useInfiniteQuery 활용
 * - IntersectionObserver API로 자동 로딩
 * - 제네릭 타입으로 재사용 가능
 * - 로딩/에러 상태 처리
 */

import { useEffect, useRef } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import type { CursorPaginatedResponse } from '../../types/sync';

export interface InfiniteScrollListProps<T> {
  queryKey: (string | number | null | undefined)[];
  fetchFn: (cursor: string | null) => Promise<CursorPaginatedResponse<T>>;
  renderItem: (item: T, index: number) => React.ReactNode;
  emptyMessage?: string;
  className?: string;
  itemClassName?: string;
}

export function InfiniteScrollList<T>({
  queryKey,
  fetchFn,
  renderItem,
  emptyMessage = '데이터가 없습니다.',
  className = '',
  itemClassName = '',
}: InfiniteScrollListProps<T>) {
  const observerTarget = useRef<HTMLDivElement>(null);

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
    error,
  } = useInfiniteQuery<CursorPaginatedResponse<T>, Error, { pages: CursorPaginatedResponse<T>[]; pageParams: (string | null)[] }, (string | number | null | undefined)[], string | null>({
    queryKey,
    queryFn: ({ pageParam }) => fetchFn(pageParam),
    getNextPageParam: (lastPage) => {
      return lastPage.has_more ? lastPage.next_cursor : undefined;
    },
    initialPageParam: null as string | null,
    staleTime: 30000, // 30초 캐시
  });

  // IntersectionObserver로 무한 스크롤 구현
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 }
    );

    const target = observerTarget.current;
    if (target) {
      observer.observe(target);
    }

    return () => {
      if (target) {
        observer.unobserve(target);
      }
    };
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // 로딩 상태
  if (isLoading) {
    return (
      <div className={`text-center py-8 ${className}`}>
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        <p className="mt-2 text-gray-500">로딩 중...</p>
      </div>
    );
  }

  // 에러 상태
  if (isError) {
    return (
      <div className={`text-center py-8 ${className}`}>
        <p className="text-red-500">데이터를 불러오는 중 오류가 발생했습니다.</p>
        <p className="text-sm text-gray-500 mt-2">
          {error instanceof Error ? error.message : '알 수 없는 오류'}
        </p>
      </div>
    );
  }

  // 데이터 추출
  const allItems = data?.pages.flatMap((page) => page.items) ?? [];
  const totalCount = data?.pages[0]?.total ?? 0;

  // 빈 상태
  if (allItems.length === 0) {
    return (
      <div className={`text-center py-8 text-gray-500 ${className}`}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={className}>
      {/* 총 개수 표시 */}
      <div className="mb-4 text-sm text-gray-500">
        전체 {totalCount.toLocaleString()}개 중 {allItems.length.toLocaleString()}개 표시
      </div>

      {/* 아이템 리스트 */}
      <div className="space-y-2">
        {allItems.map((item, index) => (
          <div key={index} className={itemClassName}>
            {renderItem(item, index)}
          </div>
        ))}
      </div>

      {/* IntersectionObserver 트리거 */}
      <div ref={observerTarget} className="py-4 text-center">
        {isFetchingNextPage ? (
          <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
        ) : hasNextPage ? (
          <button
            onClick={() => fetchNextPage()}
            className="px-4 py-2 text-sm text-blue-500 hover:text-blue-700 hover:underline"
          >
            더 보기
          </button>
        ) : (
          <p className="text-gray-400 text-sm">모든 항목을 불러왔습니다.</p>
        )}
      </div>
    </div>
  );
}
