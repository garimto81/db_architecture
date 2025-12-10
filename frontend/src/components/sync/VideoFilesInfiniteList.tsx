/**
 * VideoFilesInfiniteList - NAS 비디오 파일 무한 스크롤 목록
 * BLOCK_FRONTEND / FrontendAgent
 * Issue #28: Cursor-based Pagination
 *
 * 기능:
 * - 프로젝트 필터 드롭다운
 * - 파일 정보 표시 (display_title, resolution, version_type, scan_status)
 * - is_hidden 표시 (숨김 파일 구분)
 * - 파일 크기 포맷팅 (GB, MB)
 */

import { useState } from 'react';
import { Card } from '../common';
import { InfiniteScrollList } from './InfiniteScrollList';
import { fetchVideoFiles } from '../../services/api';
import type { VideoFileResponse } from '../../types/sync';

// 프로젝트 목록 (추후 API에서 동적으로 가져올 수 있음)
const PROJECTS = [
  'Raw Deal',
  'High Stakes Poker',
  'Poker After Dark',
  'Poker Royale',
  'NBC Heads-Up',
  'Poker Superstars',
  'Poker Dome',
];

// 파일 크기 포맷팅
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

// 스캔 상태 뱃지
function ScanStatusBadge({ status }: { status: string }) {
  const statusMap: Record<string, { label: string; color: string }> = {
    pending: { label: '대기', color: 'bg-gray-100 text-gray-700' },
    processing: { label: '처리 중', color: 'bg-blue-100 text-blue-700' },
    completed: { label: '완료', color: 'bg-green-100 text-green-700' },
    error: { label: '에러', color: 'bg-red-100 text-red-700' },
  };

  const { label, color } = statusMap[status] || { label: status, color: 'bg-gray-100 text-gray-700' };

  return (
    <span className={`px-2 py-1 text-xs rounded-full ${color}`}>
      {label}
    </span>
  );
}

// 비디오 파일 카드 컴포넌트
function VideoFileCard({ file }: { file: VideoFileResponse }) {
  return (
    <div className={`border rounded-lg p-4 hover:bg-gray-50 transition-colors ${
      file.is_hidden ? 'bg-gray-50 border-gray-300' : 'bg-white border-gray-200'
    }`}>
      <div className="flex items-start justify-between gap-4">
        {/* 왼쪽: 파일 정보 */}
        <div className="flex-1 min-w-0">
          {/* 제목 */}
          <h3 className="font-medium text-gray-900 truncate" title={file.display_title || file.file_name}>
            {file.display_title || file.file_name}
          </h3>

          {/* 메타데이터 */}
          <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
            {file.resolution && (
              <span className="flex items-center gap-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                {file.resolution}
              </span>
            )}
            {file.version_type && (
              <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                {file.version_type}
              </span>
            )}
            <span>{formatFileSize(file.file_size_bytes)}</span>
          </div>

          {/* 파일 경로 */}
          <div className="mt-2 text-xs text-gray-400 truncate" title={file.file_path}>
            {file.file_path}
          </div>

          {/* 숨김 상태 */}
          {file.is_hidden && file.hidden_reason && (
            <div className="mt-2 flex items-center gap-2 text-xs text-orange-600">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
              </svg>
              숨김: {file.hidden_reason}
            </div>
          )}
        </div>

        {/* 오른쪽: 상태 */}
        <div className="flex flex-col items-end gap-2">
          <ScanStatusBadge status={file.scan_status} />
          {file.project_name && (
            <span className="text-xs text-gray-500">{file.project_name}</span>
          )}
        </div>
      </div>
    </div>
  );
}

// 메인 컴포넌트
export function VideoFilesInfiniteList() {
  const [selectedProject, setSelectedProject] = useState<string>('');

  return (
    <Card title="📁 NAS 비디오 파일 목록">
      {/* 필터 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          프로젝트 필터
        </label>
        <select
          value={selectedProject}
          onChange={(e) => setSelectedProject(e.target.value)}
          className="w-full md:w-64 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">전체 프로젝트</option>
          {PROJECTS.map((project) => (
            <option key={project} value={project}>
              {project}
            </option>
          ))}
        </select>
      </div>

      {/* 무한 스크롤 리스트 */}
      <InfiniteScrollList<VideoFileResponse>
        queryKey={['videoFiles', selectedProject]}
        fetchFn={(cursor) => fetchVideoFiles(cursor, selectedProject || undefined)}
        renderItem={(file) => <VideoFileCard file={file} />}
        emptyMessage={
          selectedProject
            ? `"${selectedProject}" 프로젝트에 파일이 없습니다.`
            : 'NAS에 동기화된 파일이 없습니다.'
        }
      />
    </Card>
  );
}
