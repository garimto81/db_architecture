/**
 * HandClipsInfiniteList - Google Sheets Hand Clips 무한 스크롤 목록
 * BLOCK_FRONTEND / FrontendAgent
 * Issue #28: Cursor-based Pagination
 *
 * @version 1.2.0
 * @updated 2025-12-10
 * @changes Issue #28: 시트 이름 변경 - Metadata Archive 활성, iconik Metadata 보류
 *
 * 기능:
 * - 기존 HandClipsTable 대체
 * - 소스 필터: metadata_archive (iconik_metadata 보류)
 * - DB 매핑 정보 표시: hand_clips.title, hand_clips.timecode 등
 * - 무한 스크롤로 대량 데이터 처리
 */

import { useState } from 'react';
import { Card, Badge } from '../common';
import { InfiniteScrollList } from './InfiniteScrollList';
import { fetchHandClipsCursor } from '../../services/api';
import type { HandClipResponse } from '../../types/sync';

// 날짜 포맷 (상대 시간)
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

// Hand Clip 카드 컴포넌트
function HandClipCard({ clip }: { clip: HandClipResponse }) {
  // Issue #28: 시트 이름 변경 - metadata_archive 활성, iconik_metadata 보류
  // 호환성: 이전 값(hand_analysis)과 새 값(metadata_archive) 모두 지원
  const isMetadataArchive = clip.sheet_source === 'metadata_archive' || clip.sheet_source === 'hand_analysis';
  const isIconikMetadata = clip.sheet_source === 'iconik_metadata' || clip.sheet_source === 'hand_database';

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white hover:bg-gray-50 transition-colors">
      <div className="flex items-start justify-between gap-4">
        {/* 왼쪽: 클립 정보 */}
        <div className="flex-1 min-w-0">
          {/* 소스 뱃지 */}
          <div className="flex items-center gap-2 mb-2">
            <Badge
              status={isMetadataArchive ? 'running' : 'idle'}
              label={isMetadataArchive ? 'Metadata Archive' : (isIconikMetadata ? 'iconik Metadata' : clip.sheet_source)}
            />
            <span className="text-xs text-gray-400">
              Row #{clip.sheet_row_number}
            </span>
          </div>

          {/* 제목 */}
          <h3 className="font-medium text-gray-900 mb-2" title={clip.title || ''}>
            {clip.title || <span className="text-gray-400 italic">제목 없음</span>}
          </h3>

          {/* 메타데이터 */}
          <div className="flex items-center gap-4 text-sm">
            {/* 타임코드 */}
            {clip.timecode && (
              <div className="flex items-center gap-1 text-gray-600">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <code className="bg-gray-100 px-2 py-0.5 rounded text-xs">
                  {clip.timecode}
                </code>
              </div>
            )}

            {/* 등급 */}
            {clip.hand_grade && (
              <div className="flex items-center gap-1">
                <svg className="w-4 h-4 text-yellow-500" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                </svg>
                <span className="text-yellow-600 font-medium text-sm">
                  {clip.hand_grade}
                </span>
              </div>
            )}
          </div>

          {/* 노트 */}
          {clip.notes && (
            <div className="mt-3 text-sm text-gray-600 bg-gray-50 rounded p-2 border border-gray-200">
              <div className="flex items-start gap-2">
                <svg className="w-4 h-4 mt-0.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="flex-1 text-xs leading-relaxed">{clip.notes}</p>
              </div>
            </div>
          )}

          {/* DB 매핑 정보 */}
          <div className="mt-3 text-xs text-gray-400 font-mono">
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              <span>id: {clip.id.slice(0, 8)}...</span>
              {clip.title && (
                <span className="text-blue-500">hand_clips.title: "{clip.title.slice(0, 30)}{clip.title.length > 30 ? '...' : ''}"</span>
              )}
              {clip.timecode && (
                <span className="text-green-500">hand_clips.timecode: "{clip.timecode}"</span>
              )}
            </div>
          </div>
        </div>

        {/* 오른쪽: 동기화 시간 */}
        <div className="flex flex-col items-end gap-2 text-sm">
          <div className="text-gray-500 text-xs">
            {formatRelativeTime(clip.created_at)}
          </div>
        </div>
      </div>
    </div>
  );
}

// DB 매핑 다이어그램 컴포넌트 (Issue #28: 실제 시트 구조 반영)
function DbMappingDiagram() {
  return (
    <div className="bg-gradient-to-r from-green-50 to-blue-50 border border-green-200 rounded-lg p-4 mb-4">
      <h4 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
        <span className="text-lg">🔗</span>
        Google Sheets ↔ DB 매핑 구조 (Metadata Archive)
      </h4>

      {/* 시각적 매핑 다이어그램 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Google Sheets 열 */}
        <div className="bg-white rounded-lg p-3 border border-gray-200">
          <div className="flex items-center gap-2 mb-3 pb-2 border-b">
            <span className="text-xl">📊</span>
            <span className="font-semibold text-green-700">Google Sheets</span>
            <span className="text-xs text-gray-400 ml-auto">Metadata Archive</span>
          </div>
          <div className="space-y-1 text-sm font-mono">
            <div className="flex items-center gap-2 text-gray-400">
              <span className="w-6 text-center">A</span>
              <span>File No.</span>
              <span className="ml-auto text-xs">(무시)</span>
            </div>
            <div className="flex items-center gap-2 bg-blue-50 rounded px-1 py-0.5">
              <span className="w-6 text-center text-blue-600 font-bold">B</span>
              <span className="text-blue-700">File Name</span>
              <span className="ml-auto">→</span>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <span className="w-6 text-center">C</span>
              <span>Nas Folder Link</span>
              <span className="ml-auto text-xs">(추후)</span>
            </div>
            <div className="flex items-center gap-2 bg-green-50 rounded px-1 py-0.5">
              <span className="w-6 text-center text-green-600 font-bold">D</span>
              <span className="text-green-700">In (타임코드)</span>
              <span className="ml-auto">→</span>
            </div>
            <div className="flex items-center gap-2 bg-purple-50 rounded px-1 py-0.5">
              <span className="w-6 text-center text-purple-600 font-bold">E</span>
              <span className="text-purple-700">Out (종료)</span>
              <span className="ml-auto">→</span>
            </div>
            <div className="flex items-center gap-2 bg-yellow-50 rounded px-1 py-0.5">
              <span className="w-6 text-center text-yellow-600 font-bold">F</span>
              <span className="text-yellow-700">Hand Grade</span>
              <span className="ml-auto">→</span>
            </div>
            <div className="flex items-center gap-2 bg-orange-50 rounded px-1 py-0.5">
              <span className="w-6 text-center text-orange-600 font-bold">G</span>
              <span className="text-orange-700">Winner</span>
              <span className="ml-auto">→</span>
            </div>
            <div className="flex items-center gap-2 text-gray-500">
              <span className="w-6 text-center">H</span>
              <span>Hands (88 vs JJ)</span>
              <span className="ml-auto text-xs">(추후)</span>
            </div>
            <div className="flex items-center gap-2 text-gray-500">
              <span className="w-6 text-center">I-K</span>
              <span>Tag (Player) 1-3</span>
              <span className="ml-auto text-xs">(추후)</span>
            </div>
            <div className="flex items-center gap-2 text-gray-500">
              <span className="w-6 text-center">L-R</span>
              <span>Tag (Poker Play) 1-7</span>
              <span className="ml-auto text-xs">(추후)</span>
            </div>
          </div>
        </div>

        {/* DB 컬럼 */}
        <div className="bg-white rounded-lg p-3 border border-gray-200">
          <div className="flex items-center gap-2 mb-3 pb-2 border-b">
            <span className="text-xl">🗄️</span>
            <span className="font-semibold text-blue-700">PostgreSQL</span>
            <span className="text-xs text-gray-400 ml-auto">hand_clips 테이블</span>
          </div>
          <div className="space-y-1 text-sm font-mono">
            <div className="flex items-center gap-2 text-gray-400">
              <span>←</span>
              <span>id</span>
              <span className="ml-auto text-xs">UUID (자동생성)</span>
            </div>
            <div className="flex items-center gap-2 bg-blue-50 rounded px-1 py-0.5">
              <span>←</span>
              <code className="text-blue-600 font-bold">title</code>
              <span className="ml-auto text-xs text-gray-500">VARCHAR(500)</span>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <span>←</span>
              <span>sheet_row_number</span>
              <span className="ml-auto text-xs">INT (행 번호)</span>
            </div>
            <div className="flex items-center gap-2 bg-green-50 rounded px-1 py-0.5">
              <span>←</span>
              <code className="text-green-600 font-bold">timecode</code>
              <span className="ml-auto text-xs text-gray-500">VARCHAR(20)</span>
            </div>
            <div className="flex items-center gap-2 bg-purple-50 rounded px-1 py-0.5">
              <span>←</span>
              <code className="text-purple-600 font-bold">timecode_end</code>
              <span className="ml-auto text-xs text-gray-500">VARCHAR(20)</span>
            </div>
            <div className="flex items-center gap-2 bg-yellow-50 rounded px-1 py-0.5">
              <span>←</span>
              <code className="text-yellow-600 font-bold">hand_grade</code>
              <span className="ml-auto text-xs text-gray-500">VARCHAR(10)</span>
            </div>
            <div className="flex items-center gap-2 bg-orange-50 rounded px-1 py-0.5">
              <span>←</span>
              <code className="text-orange-600 font-bold">notes</code>
              <span className="ml-auto text-xs text-gray-500">TEXT</span>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <span>←</span>
              <span>sheet_source</span>
              <span className="ml-auto text-xs">metadata_archive</span>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <span>←</span>
              <span>is_active</span>
              <span className="ml-auto text-xs">BOOLEAN</span>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <span>←</span>
              <span>created_at</span>
              <span className="ml-auto text-xs">TIMESTAMP</span>
            </div>
          </div>
        </div>
      </div>

      {/* 범례 */}
      <div className="mt-3 flex flex-wrap gap-3 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-blue-200"></div>
          <span>제목</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-green-200"></div>
          <span>시작 타임코드</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-purple-200"></div>
          <span>종료 타임코드</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-yellow-200"></div>
          <span>등급</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-orange-200"></div>
          <span>승자</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-gray-200"></div>
          <span>미구현/자동</span>
        </div>
      </div>
    </div>
  );
}

// 메인 컴포넌트
export function HandClipsInfiniteList() {
  const [selectedSource, setSelectedSource] = useState<string>('');
  const [showMapping, setShowMapping] = useState(true);

  return (
    <Card title="🎬 Hand Clips 상세 목록 - DB 연동 뷰">
      {/* 필터 및 토글 */}
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            시트 소스 필터
          </label>
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="w-full md:w-64 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">전체 소스</option>
            <option value="metadata_archive">Metadata Archive</option>
            {/* iconik Metadata - 사용 보류 */}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">매핑 다이어그램</label>
          <button
            onClick={() => setShowMapping(!showMapping)}
            className={`px-3 py-1 text-sm rounded-full transition-colors ${
              showMapping
                ? 'bg-blue-100 text-blue-700 border border-blue-300'
                : 'bg-gray-100 text-gray-600 border border-gray-300'
            }`}
          >
            {showMapping ? '✓ 표시' : '숨김'}
          </button>
        </div>
      </div>

      {/* DB 매핑 다이어그램 */}
      {showMapping && <DbMappingDiagram />}

      {/* 증분 동기화 안내 */}
      <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm">
        <div className="flex items-start gap-2">
          <span className="text-blue-500 text-lg">ℹ️</span>
          <div className="text-blue-700">
            <strong>DB 매핑 정보 안내</strong>
            <ul className="mt-1 text-xs space-y-1 text-blue-600">
              <li>• <span className="text-blue-500 font-mono">파란색</span>: hand_clips.title 컬럼</li>
              <li>• <span className="text-green-500 font-mono">초록색</span>: hand_clips.timecode 컬럼</li>
              <li>• 각 항목 하단에 실제 저장된 DB 컬럼값이 표시됩니다</li>
            </ul>
          </div>
        </div>
      </div>

      {/* 무한 스크롤 리스트 */}
      <InfiniteScrollList<HandClipResponse>
        queryKey={['handClipsCursor', selectedSource]}
        fetchFn={(cursor) => fetchHandClipsCursor(cursor, selectedSource || undefined)}
        renderItem={(clip) => <HandClipCard clip={clip} />}
        emptyMessage={
          selectedSource
            ? `"${selectedSource}" 소스에 클립이 없습니다.`
            : '동기화된 Hand Clips가 없습니다.'
        }
      />
    </Card>
  );
}
