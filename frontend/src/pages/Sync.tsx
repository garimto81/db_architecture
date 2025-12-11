/**
 * Sync Page - 동기화 상세 페이지
 * BLOCK_FRONTEND / FrontendAgent
 *
 * @version 1.6.0
 * @updated 2025-12-11
 * @changes Issue #30: Nas Folder Link → video_file_id 연결 구현
 */

// 페이지 버전 정보 (UI 하단에 표시)
const PAGE_VERSION = {
  version: '1.6.0',
  updated: '2025-12-11',
  changes: 'Issue #30: Nas Folder Link → video_file_id 연결 완료 (97.4%)',
};

import { Card, Button, Badge, ProgressBar } from '../components/common';
import { DataBrowser, SheetsViewer } from '../components/sync';
import { useSyncStore } from '../store';
import { useSyncHistory, useTriggerSync, useSyncWebSocket } from '../hooks';
import { useState } from 'react';

type SyncTab = 'status' | 'files' | 'sheets';

export function Sync() {
  const [page, setPage] = useState(1);
  const [activeTab, setActiveTab] = useState<SyncTab>('status');

  // WebSocket 연결
  useSyncWebSocket();

  // Store 상태
  const {
    nasStatus,
    nasLastSync,
    nasProgress,
    nasFilesCount,
    nasCurrentFile,
    sheetsStatus,
    sheetsLastSync,
    sheetsProgress,
    sheetsRowsCount,
  } = useSyncStore();

  // API 데이터
  const { data: history, isLoading: isHistoryLoading } = useSyncHistory(page);
  const triggerSync = useTriggerSync();

  const formatDate = (date: Date | null) => {
    if (!date) return '-';
    return new Intl.DateTimeFormat('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(date);
  };

  const tabs: { key: SyncTab; label: string; icon: string }[] = [
    { key: 'status', label: '동기화 상태', icon: '🔄' },
    { key: 'files', label: '파일 브라우저', icon: '📂' },
    { key: 'sheets', label: 'Sheets 데이터', icon: '📊' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Sync Management</h2>
        <p className="text-gray-500 mt-1">동기화 상태 관리 및 데이터 검수</p>
        <div className="mt-2 text-xs text-gray-400 flex items-center gap-2">
          <span className="bg-gray-100 px-2 py-0.5 rounded">
            📋 v{PAGE_VERSION.version}
          </span>
          <span>{PAGE_VERSION.updated}</span>
          <span className="text-gray-300">|</span>
          <span>{PAGE_VERSION.changes}</span>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-t-lg font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'files' && <DataBrowser />}
      {activeTab === 'sheets' && <SheetsViewer />}

      {/* Status Tab Content */}
      {activeTab === 'status' && (
        <>
      {/* Sync Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* NAS Sync Panel */}
        <Card title="📁 NAS 동기화">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-500">상태</span>
              <Badge status={nasStatus} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-500">마지막 동기화</span>
              <span className="font-medium">{formatDate(nasLastSync)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-500">총 파일 수</span>
              <span className="font-medium">{nasFilesCount.toLocaleString()}</span>
            </div>

            {nasStatus === 'running' && (
              <div className="pt-2">
                <ProgressBar progress={nasProgress} showLabel />
                {nasCurrentFile && (
                  <p className="mt-1 text-xs text-gray-500 truncate">{nasCurrentFile}</p>
                )}
              </div>
            )}

            <Button
              onClick={() => triggerSync.mutate('nas')}
              disabled={nasStatus === 'running'}
              loading={triggerSync.isPending && triggerSync.variables === 'nas'}
              className="w-full mt-4"
            >
              🔄 NAS 동기화 시작
            </Button>
          </div>
        </Card>

        {/* Sheets Sync Panel */}
        <Card title="📊 Google Sheets 동기화">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-500">상태</span>
              <Badge status={sheetsStatus} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-500">마지막 동기화</span>
              <span className="font-medium">{formatDate(sheetsLastSync)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-500">총 행 수</span>
              <span className="font-medium">{sheetsRowsCount.toLocaleString()}</span>
            </div>

            {sheetsStatus === 'running' && (
              <div className="pt-2">
                <ProgressBar progress={sheetsProgress} showLabel />
              </div>
            )}

            <Button
              onClick={() => triggerSync.mutate('sheets')}
              disabled={sheetsStatus === 'running'}
              loading={triggerSync.isPending && triggerSync.variables === 'sheets'}
              className="w-full mt-4"
            >
              🔄 Sheets 동기화 시작
            </Button>
          </div>
        </Card>
      </div>

      {/* Sync History */}
      <Card title="📜 동기화 히스토리">
        {isHistoryLoading ? (
          <div className="animate-pulse space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="bg-gray-200 rounded h-10" />
            ))}
          </div>
        ) : history && history.items.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      시간
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      소스
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      상태
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      메시지
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {history.items.map((log) => (
                    <tr key={log.id}>
                      <td className="px-4 py-2 text-sm text-gray-600">
                        {new Date(log.timestamp).toLocaleString('ko-KR')}
                      </td>
                      <td className="px-4 py-2 text-sm font-medium">
                        {log.source.toUpperCase()}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                            log.type === 'complete'
                              ? 'bg-green-100 text-green-800'
                              : log.type === 'error'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {log.type}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-600">{log.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {history.total_pages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <span className="text-sm text-gray-500">
                  Page {history.page} of {history.total_pages}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    이전
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPage((p) => Math.min(history.total_pages, p + 1))}
                    disabled={page === history.total_pages}
                  >
                    다음
                  </Button>
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="text-center text-gray-500 py-8">동기화 히스토리가 없습니다.</p>
        )}
      </Card>
        </>
      )}

    </div>
  );
}
