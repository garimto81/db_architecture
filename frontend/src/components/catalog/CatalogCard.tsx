/**
 * CatalogCard - 개별 비디오 카드 컴포넌트
 * BLOCK_FRONTEND / FrontendAgent
 */

import type { CatalogItem } from '../../types/catalog';
import { PROJECT_COLORS, FORMAT_LABELS } from '../../types/catalog';

interface CatalogCardProps {
  item: CatalogItem;
  onClick?: (item: CatalogItem) => void;
}

/**
 * 파일 크기를 사람이 읽기 좋은 형식으로 변환
 */
function formatFileSize(bytes: number | null): string {
  if (!bytes) return '-';
  const gb = bytes / (1024 * 1024 * 1024);
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(0)} MB`;
}

/**
 * 초 단위 시간을 HH:MM:SS 형식으로 변환
 */
function formatDuration(seconds: number | null): string {
  if (!seconds) return '-';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * 표시할 제목 결정
 */
function getDisplayTitle(item: CatalogItem): string {
  return item.display_title || item.episode_title || item.file_name;
}

export function CatalogCard({ item, onClick }: CatalogCardProps) {
  const projectColor = item.project_code
    ? PROJECT_COLORS[item.project_code] || PROJECT_COLORS.OTHER
    : PROJECT_COLORS.OTHER;

  const formatLabel = item.file_format
    ? FORMAT_LABELS[item.file_format.toLowerCase()] || item.file_format.toUpperCase()
    : null;

  return (
    <div
      className={`
        group relative bg-gray-800 rounded-lg overflow-hidden
        transition-all duration-300 hover:scale-105 hover:shadow-xl
        cursor-pointer border border-gray-700 hover:border-blue-500
      `}
      onClick={() => onClick?.(item)}
    >
      {/* 썸네일 영역 (플레이스홀더) */}
      <div className="relative aspect-video bg-gray-900 flex items-center justify-center">
        {/* 프로젝트 뱃지 */}
        {item.project_code && (
          <span
            className={`absolute top-2 left-2 px-2 py-0.5 text-xs font-bold rounded ${projectColor} text-white`}
          >
            {item.project_code}
          </span>
        )}

        {/* 연도 */}
        {item.year && (
          <span className="absolute top-2 right-2 px-2 py-0.5 text-xs bg-black/60 rounded text-gray-300">
            {item.year}
          </span>
        )}

        {/* 비디오 아이콘 */}
        <svg
          className="w-16 h-16 text-gray-600 group-hover:text-gray-500 transition-colors"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm3 2h6v4H7V5zm8 8v2h2v-2h-2zm0-2v-2h2v2h-2zm0-4V5h2v2h-2zM5 7v2H3V7h2zm0 4v2H3v-2h2zm0 4v-2H3v2h2zm2 0h6v-2H7v2z"
            clipRule="evenodd"
          />
        </svg>

        {/* 재생 시간 */}
        {item.duration_seconds && (
          <span className="absolute bottom-2 right-2 px-1.5 py-0.5 text-xs bg-black/80 rounded text-white">
            {formatDuration(item.duration_seconds)}
          </span>
        )}

        {/* Hidden 표시 */}
        {item.is_hidden && (
          <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
            <span className="px-2 py-1 bg-red-500/80 rounded text-xs text-white">Hidden</span>
          </div>
        )}
      </div>

      {/* 정보 영역 */}
      <div className="p-3">
        {/* 제목 */}
        <h3
          className="text-sm font-medium text-white truncate group-hover:text-blue-400 transition-colors"
          title={getDisplayTitle(item)}
        >
          {getDisplayTitle(item)}
        </h3>

        {/* 이벤트명 */}
        {item.event_name && (
          <p className="text-xs text-gray-400 truncate mt-0.5" title={item.event_name}>
            {item.event_name}
          </p>
        )}

        {/* 메타데이터 행 */}
        <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
          {formatLabel && (
            <span className="px-1.5 py-0.5 bg-gray-700 rounded">{formatLabel}</span>
          )}
          {item.resolution && (
            <span className="px-1.5 py-0.5 bg-gray-700 rounded">{item.resolution}</span>
          )}
          <span className="ml-auto">{formatFileSize(item.file_size_bytes)}</span>
        </div>

        {/* 버전 타입 */}
        {item.version_type && (
          <div className="mt-2">
            <span className="px-1.5 py-0.5 text-xs bg-blue-600/30 text-blue-300 rounded">
              {item.version_type}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export default CatalogCard;
