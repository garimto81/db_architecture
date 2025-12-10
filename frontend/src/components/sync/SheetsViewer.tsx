/**
 * SheetsViewer - Google Sheets 동기화 데이터 뷰어
 * BLOCK_FRONTEND / FrontendAgent
 * Issue #23: 동기화된 구글 시트 데이터 표시
 *
 * @version 1.3.0
 * @updated 2025-12-10
 * @changes Issue #28: 시트 이름 변경 반영 - Metadata Archive 활성
 *
 * v1.2.0: HandClipsInfiniteList 연동 (DB 매핑 뷰)
 * v1.1.0: Hand Clips 검증 대시보드 추가 (LLD 02 Section 9)
 * - SyncSummaryCard: 동기화 현황 요약
 * - HandClipsTable: 상세 목록 (페이지네이션)
 * - 증분 동기화 설명 UI
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Badge } from '../common';
import { apiClient } from '../../services/api';
import { HandClipsInfiniteList } from './HandClipsInfiniteList';
import type {
  SheetPreviewResponse,
  SchedulerStatusResponse,
  HandClipsSummaryResponse,
  HandClipsListResponse,
} from '../../types/sync';

// API 호출 함수
async function fetchSheetsPreview(): Promise<SheetPreviewResponse> {
  const response = await apiClient.get<SheetPreviewResponse>('/api/sync/sheets/preview');
  return response.data;
}

async function fetchSchedulerStatus(): Promise<SchedulerStatusResponse> {
  const response = await apiClient.get<SchedulerStatusResponse>('/api/sync/scheduler');
  return response.data;
}

async function fetchHandClipsSummary(): Promise<HandClipsSummaryResponse> {
  const response = await apiClient.get<HandClipsSummaryResponse>('/api/sync/hand-clips/summary');
  return response.data;
}

async function fetchHandClipsList(
  source: string | null,
  page: number,
  pageSize: number
): Promise<HandClipsListResponse> {
  const params = new URLSearchParams();
  if (source) params.set('source', source);
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  const response = await apiClient.get<HandClipsListResponse>(`/api/sync/hand-clips?${params}`);
  return response.data;
}

// 날짜 포맷
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(dateStr));
}

// 상대 시간 포맷 (예: "2시간 전")
function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHour = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return '방금 전';
  if (diffMin < 60) return `${diffMin}분 전`;
  if (diffHour < 24) return `${diffHour}시간 전`;
  return `${diffDay}일 전`;
}

// ============== SyncSummaryCard: 동기화 현황 요약 ==============
function SyncSummaryCard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['handClipsSummary'],
    queryFn: fetchHandClipsSummary,
    staleTime: 30000, // 30초 캐시
  });

  if (isLoading) {
    return (
      <Card title="📊 Hand Clips 동기화 현황">
        <div className="text-center text-gray-500 py-4">로딩 중...</div>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card title="📊 Hand Clips 동기화 현황">
        <div className="text-center text-red-500 py-4">데이터를 불러올 수 없습니다.</div>
      </Card>
    );
  }

  return (
    <Card title="📊 Hand Clips 동기화 현황">
      <div className="space-y-4">
        {/* 요약 통계 */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-blue-50 rounded-lg p-4 text-center">
            <div className="text-3xl font-bold text-blue-600">
              {data.total_clips.toLocaleString()}
            </div>
            <div className="text-sm text-blue-500 mt-1">전체 클립</div>
          </div>
          <div className="bg-green-50 rounded-lg p-4 text-center">
            <div className="text-3xl font-bold text-green-600">
              {formatRelativeTime(data.latest_sync)}
            </div>
            <div className="text-sm text-green-500 mt-1">마지막 동기화</div>
          </div>
        </div>

        {/* 소스별 통계 */}
        <div className="space-y-2">
          {Object.entries(data.by_source).map(([source, count]) => (
            <div
              key={source}
              className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
            >
              <div className="flex items-center gap-2">
                <Badge
                  status={source === 'hand_analysis' ? 'running' : 'idle'}
                  label={source === 'hand_analysis' ? 'Analysis' : 'Database'}
                />
                <span className="text-gray-600">{source}</span>
              </div>
              <span className="font-medium">{count.toLocaleString()} clips</span>
            </div>
          ))}
        </div>

        {/* 증분 동기화 설명 */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm">
          <div className="flex items-start gap-2">
            <span className="text-blue-500">ℹ️</span>
            <div className="text-blue-700">
              <strong>증분 동기화 안내</strong>
              <ul className="mt-1 text-xs space-y-1 text-blue-600">
                <li>• 이미 동기화된 행은 다시 처리하지 않습니다</li>
                <li>• "0개 추가"는 새 행이 없다는 의미입니다</li>
                <li>• 실제 데이터는 아래 테이블에서 확인하세요</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

// ============== HandClipsTable: 상세 목록 ==============
function HandClipsTable() {
  const [page, setPage] = useState(1);
  const [source, setSource] = useState<string | null>(null);
  const pageSize = 15;

  const { data, isLoading } = useQuery({
    queryKey: ['handClipsList', source, page, pageSize],
    queryFn: () => fetchHandClipsList(source, page, pageSize),
    staleTime: 30000,
  });

  return (
    <Card title="📋 Hand Clips 상세 목록">
      {/* 필터 */}
      <div className="flex gap-4 mb-4">
        <select
          value={source || ''}
          onChange={(e) => {
            setSource(e.target.value || null);
            setPage(1);
          }}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">전체 소스</option>
          <option value="hand_analysis">Hand Analysis</option>
          <option value="hand_database">Hand Database</option>
        </select>
        {data && (
          <span className="text-sm text-gray-500 self-center">
            총 {data.total.toLocaleString()}개
          </span>
        )}
      </div>

      {/* 테이블 */}
      {isLoading ? (
        <div className="text-center text-gray-500 py-8">로딩 중...</div>
      ) : data && data.items.length > 0 ? (
        <>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-24">
                    소스
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    제목
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-24">
                    타임코드
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-20">
                    등급
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-28">
                    동기화
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.map((clip) => (
                  <tr key={clip.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2">
                      <Badge
                        status={clip.sheet_source === 'hand_analysis' ? 'running' : 'idle'}
                        label={clip.sheet_source === 'hand_analysis' ? 'A' : 'D'}
                      />
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-900 max-w-xs truncate" title={clip.title || ''}>
                      {clip.title || '-'}
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <code className="bg-gray-100 px-1 rounded text-xs">
                        {clip.timecode || '-'}
                      </code>
                    </td>
                    <td className="px-3 py-2 text-sm">
                      {clip.hand_grade && (
                        <span className="text-yellow-500">{clip.hand_grade}</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {formatRelativeTime(clip.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 페이지네이션 */}
          <div className="flex justify-between items-center mt-4 pt-4 border-t">
            <span className="text-sm text-gray-500">
              페이지 {data.page} / {data.total_pages}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 text-sm border rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                이전
              </button>
              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page >= data.total_pages}
                className="px-3 py-1 text-sm border rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                다음
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center text-gray-500 py-8">
          동기화된 데이터가 없습니다.
        </div>
      )}
    </Card>
  );
}

// 시트 탭 컴포넌트
function SheetTabs({
  sheets,
  activeSheet,
  onSelect,
}: {
  sheets: Record<string, { sheet_name: string; row_count: number }>;
  activeSheet: string;
  onSelect: (key: string) => void;
}) {
  return (
    <div className="flex gap-2 mb-4">
      {Object.entries(sheets).map(([key, info]) => (
        <button
          key={key}
          onClick={() => onSelect(key)}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeSheet === key
              ? 'bg-blue-500 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          {info.sheet_name}
          <span className="ml-2 text-xs opacity-75">({info.row_count}행)</span>
        </button>
      ))}
    </div>
  );
}

// 스케줄러 상태 카드
function SchedulerCard() {
  const { data, isLoading } = useQuery({
    queryKey: ['schedulerStatus'],
    queryFn: fetchSchedulerStatus,
    refetchInterval: 60000, // 1분마다 갱신
  });

  if (isLoading) {
    return (
      <Card title="⏰ 스케줄러 상태">
        <div className="text-center text-gray-500 py-4">로딩 중...</div>
      </Card>
    );
  }

  return (
    <Card title="⏰ 스케줄러 상태">
      <div className="space-y-4">
        {/* 스케줄러 상태 */}
        <div className="flex items-center justify-between">
          <span className="text-gray-500">APScheduler</span>
          <Badge
            status={data?.is_running ? 'running' : 'idle'}
            label={data?.is_running ? '실행 중' : '중지됨'}
          />
        </div>

        {/* 다음 동기화 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">다음 NAS 동기화</span>
            <span className="font-medium">{formatDate(data?.next_nas_sync ?? null)}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">다음 Sheets 동기화</span>
            <span className="font-medium">{formatDate(data?.next_sheets_sync ?? null)}</span>
          </div>
        </div>

        {/* 작업 목록 */}
        {data?.jobs && data.jobs.length > 0 && (
          <div className="border-t pt-3">
            <h4 className="text-sm font-medium text-gray-700 mb-2">등록된 작업</h4>
            <div className="space-y-2">
              {data.jobs.map((job) => (
                <div
                  key={job.job_id}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-gray-600">{job.name}</span>
                  <div className="flex items-center gap-2">
                    <code className="text-xs bg-gray-100 px-1 rounded">
                      {job.cron_expression}
                    </code>
                    <Badge
                      status={job.enabled ? 'idle' : 'error'}
                      label={job.enabled ? '활성' : '비활성'}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

// 메인 컴포넌트
export function SheetsViewer() {
  const [activeSheet, setActiveSheet] = useState<string>('hand_analysis');
  const [viewMode, setViewMode] = useState<'dbMapping' | 'summary' | 'detail' | 'raw'>('dbMapping');

  const { data, isLoading, error } = useQuery({
    queryKey: ['sheetsPreview'],
    queryFn: fetchSheetsPreview,
    staleTime: 60000, // 1분 캐시
  });

  const currentSheet = data?.sheets?.[activeSheet];

  return (
    <div className="space-y-4">
      {/* 뷰 모드 선택 */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setViewMode('dbMapping')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            viewMode === 'dbMapping'
              ? 'bg-blue-500 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          🔗 DB 매핑 뷰
        </button>
        <button
          onClick={() => setViewMode('summary')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            viewMode === 'summary'
              ? 'bg-blue-500 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          📊 요약
        </button>
        <button
          onClick={() => setViewMode('detail')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            viewMode === 'detail'
              ? 'bg-blue-500 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          📋 상세 목록
        </button>
        <button
          onClick={() => setViewMode('raw')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            viewMode === 'raw'
              ? 'bg-blue-500 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          🔧 원시 데이터
        </button>
      </div>

      {/* DB 매핑 뷰 (기본) - Issue #28 */}
      {viewMode === 'dbMapping' && <HandClipsInfiniteList />}

      {/* 요약 뷰 */}
      {viewMode === 'summary' && (
        <>
          <SyncSummaryCard />
          <SchedulerCard />
        </>
      )}

      {/* 상세 목록 뷰 */}
      {viewMode === 'detail' && <HandClipsTable />}

      {/* 원시 데이터 뷰 (기존) */}
      {viewMode === 'raw' && (
        <Card title="🔧 Google Sheets 원시 데이터">
        {isLoading ? (
          <div className="text-center text-gray-500 py-8">로딩 중...</div>
        ) : error ? (
          <div className="text-center text-red-500 py-8">
            데이터를 불러오는 중 오류가 발생했습니다.
          </div>
        ) : data ? (
          <>
            {/* 탭 */}
            <SheetTabs
              sheets={Object.fromEntries(
                Object.entries(data.sheets).map(([k, v]) => [
                  k,
                  { sheet_name: v.sheet_name, row_count: v.row_count },
                ])
              )}
              activeSheet={activeSheet}
              onSelect={setActiveSheet}
            />

            {/* 시트 정보 */}
            {currentSheet && (
              <div className="mb-4 text-sm text-gray-500 flex gap-4">
                <span>마지막 동기화: {formatDate(currentSheet.last_synced_at)}</span>
                <span>동기화된 행: {currentSheet.last_row_synced.toLocaleString()}</span>
              </div>
            )}

            {/* 데이터 테이블 */}
            {currentSheet?.sample_data && currentSheet.sample_data.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        제목
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        타임코드
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        등급
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        동기화일
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {currentSheet.sample_data.map((row) => (
                      <tr key={row.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-sm text-gray-900">
                          {row.title || '-'}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-600">
                          <code className="bg-gray-100 px-1 rounded">
                            {row.timecode || '-'}
                          </code>
                        </td>
                        <td className="px-4 py-2 text-sm">
                          {row.hand_grade && (
                            <span className="text-yellow-500">{row.hand_grade}</span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-500">
                          {formatDate(row.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                동기화된 데이터가 없습니다.
              </div>
            )}

            {/* 총계 */}
            <div className="mt-4 text-sm text-gray-500 text-right">
              전체 동기화 행: {data.total_synced_rows.toLocaleString()}개
            </div>
          </>
        ) : null}
        </Card>
      )}
    </div>
  );
}
