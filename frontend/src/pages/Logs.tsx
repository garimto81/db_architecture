/**
 * Logs Page - 로그 뷰어 페이지 (검색 및 필터링 지원)
 * BLOCK_FRONTEND / FrontendAgent
 */

import { useState, useMemo } from 'react';
import { Card, SearchInput, Select, Button } from '../components/common';
import { useSyncStore } from '../store';
import { useSyncWebSocket } from '../hooks';
import type { SyncLogEntry, SyncSource } from '../types';

// 필터 옵션
const sourceOptions = [
  { value: '', label: '모든 소스' },
  { value: 'nas', label: 'NAS' },
  { value: 'sheets', label: 'Google Sheets' },
];

const typeOptions = [
  { value: '', label: '모든 유형' },
  { value: 'start', label: '시작' },
  { value: 'complete', label: '완료' },
  { value: 'error', label: '에러' },
];

export function Logs() {
  // WebSocket 연결
  useSyncWebSocket();

  // Store 상태
  const { recentLogs, clearLogs } = useSyncStore();

  // 필터 상태
  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  // 필터링된 로그
  const filteredLogs = useMemo(() => {
    return recentLogs.filter((log) => {
      // 소스 필터
      if (sourceFilter && log.source !== sourceFilter) {
        return false;
      }

      // 타입 필터
      if (typeFilter && log.type !== typeFilter) {
        return false;
      }

      // 검색어 필터 (메시지, 소스, 타입에서 검색)
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesMessage = log.message.toLowerCase().includes(query);
        const matchesSource = log.source.toLowerCase().includes(query);
        const matchesType = log.type.toLowerCase().includes(query);
        const matchesDetails = log.details
          ? JSON.stringify(log.details).toLowerCase().includes(query)
          : false;

        if (!matchesMessage && !matchesSource && !matchesType && !matchesDetails) {
          return false;
        }
      }

      return true;
    });
  }, [recentLogs, searchQuery, sourceFilter, typeFilter]);

  // 필터 초기화
  const handleClearFilters = () => {
    setSearchQuery('');
    setSourceFilter('');
    setTypeFilter('');
  };

  const hasActiveFilters = searchQuery || sourceFilter || typeFilter;

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'start':
        return '▶️';
      case 'complete':
        return '✅';
      case 'error':
        return '❌';
      default:
        return '📝';
    }
  };

  const getTypeClass = (type: string) => {
    switch (type) {
      case 'complete':
        return 'bg-green-50 border-green-200';
      case 'error':
        return 'bg-red-50 border-red-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const renderLogItem = (log: SyncLogEntry) => (
    <div
      key={log.id}
      className={`p-4 rounded-lg border ${getTypeClass(log.type)}`}
    >
      <div className="flex items-start gap-3">
        <span className="text-xl">{getTypeIcon(log.type)}</span>
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <span className="font-medium text-gray-900">{log.message}</span>
            <span className="text-xs text-gray-500">
              {new Date(log.timestamp).toLocaleString('ko-KR')}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                log.source === 'nas'
                  ? 'bg-blue-100 text-blue-800'
                  : 'bg-purple-100 text-purple-800'
              }`}
            >
              {log.source.toUpperCase()}
            </span>
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
          </div>
          {log.details && (
            <pre className="mt-2 text-xs text-gray-600 bg-white p-2 rounded overflow-x-auto">
              {JSON.stringify(log.details, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Logs</h2>
          <p className="text-gray-500 mt-1">
            실시간 동기화 로그 ({filteredLogs.length}/{recentLogs.length}개)
          </p>
        </div>
        <button
          onClick={clearLogs}
          className="text-sm text-gray-500 hover:text-gray-700 underline"
        >
          로그 지우기
        </button>
      </div>

      {/* Filters */}
      <Card>
        <div className="flex flex-col md:flex-row gap-4">
          {/* 검색 */}
          <div className="flex-1">
            <SearchInput
              placeholder="메시지, 소스, 상세 정보 검색..."
              value={searchQuery}
              onChange={setSearchQuery}
              debounceMs={200}
            />
          </div>

          {/* 소스 필터 */}
          <div className="w-full md:w-40">
            <Select
              options={sourceOptions}
              value={sourceFilter}
              onChange={(value) => setSourceFilter(value as SyncSource | '')}
              placeholder="소스 선택"
            />
          </div>

          {/* 타입 필터 */}
          <div className="w-full md:w-40">
            <Select
              options={typeOptions}
              value={typeFilter}
              onChange={setTypeFilter}
              placeholder="유형 선택"
            />
          </div>

          {/* 필터 초기화 */}
          {hasActiveFilters && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleClearFilters}
              className="whitespace-nowrap"
            >
              필터 초기화
            </Button>
          )}
        </div>
      </Card>

      {/* Log List */}
      <Card>
        {recentLogs.length === 0 ? (
          <div className="text-center py-12">
            <span className="text-4xl">📋</span>
            <p className="mt-4 text-gray-500">표시할 로그가 없습니다.</p>
            <p className="text-sm text-gray-400 mt-1">
              동기화가 시작되면 로그가 여기에 표시됩니다.
            </p>
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="text-center py-12">
            <span className="text-4xl">🔍</span>
            <p className="mt-4 text-gray-500">검색 결과가 없습니다.</p>
            <p className="text-sm text-gray-400 mt-1">
              다른 검색어나 필터를 시도해 보세요.
            </p>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleClearFilters}
              className="mt-4"
            >
              필터 초기화
            </Button>
          </div>
        ) : (
          <div className="space-y-3">{filteredLogs.map(renderLogItem)}</div>
        )}
      </Card>
    </div>
  );
}
