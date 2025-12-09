/**
 * SheetsViewer - Google Sheets 동기화 데이터 뷰어
 * BLOCK_FRONTEND / FrontendAgent
 * Issue #23: 동기화된 구글 시트 데이터 표시
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Badge } from '../common';
import { apiClient } from '../../services/api';
import type { SheetPreviewResponse, SchedulerStatusResponse } from '../../types/sync';

// API 호출 함수
async function fetchSheetsPreview(): Promise<SheetPreviewResponse> {
  const response = await apiClient.get<SheetPreviewResponse>('/api/sync/sheets/preview');
  return response.data;
}

async function fetchSchedulerStatus(): Promise<SchedulerStatusResponse> {
  const response = await apiClient.get<SchedulerStatusResponse>('/api/sync/scheduler');
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

  const { data, isLoading, error } = useQuery({
    queryKey: ['sheetsPreview'],
    queryFn: fetchSheetsPreview,
    staleTime: 60000, // 1분 캐시
  });

  const currentSheet = data?.sheets?.[activeSheet];

  return (
    <div className="space-y-4">
      {/* 스케줄러 상태 */}
      <SchedulerCard />

      {/* 시트 데이터 */}
      <Card title="📊 Google Sheets 데이터">
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
    </div>
  );
}
