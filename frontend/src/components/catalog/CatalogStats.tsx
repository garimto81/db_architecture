/**
 * CatalogStats - 카탈로그 통계 컴포넌트
 * BLOCK_FRONTEND / FrontendAgent
 */

import type { CatalogStats as CatalogStatsType } from '../../types/catalog';
import { Card } from '../common';

interface CatalogStatsProps {
  stats: CatalogStatsType | null;
  isLoading?: boolean;
}

/**
 * 통계 카드 컴포넌트
 */
function StatCard({
  label,
  value,
  subValue,
}: {
  label: string;
  value: string | number;
  subValue?: string;
}) {
  return (
    <div className="text-center">
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-sm text-gray-400">{label}</p>
      {subValue && <p className="text-xs text-gray-500 mt-1">{subValue}</p>}
    </div>
  );
}

export function CatalogStats({ stats, isLoading = false }: CatalogStatsProps) {
  if (isLoading || !stats) {
    return (
      <Card className="mb-6">
        <div className="flex justify-around py-4 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="text-center">
              <div className="h-8 w-16 bg-gray-700 rounded mx-auto mb-2" />
              <div className="h-4 w-20 bg-gray-700 rounded" />
            </div>
          ))}
        </div>
      </Card>
    );
  }

  const formatDuration = (hours: number | null) => {
    if (!hours) return '-';
    if (hours >= 24) {
      const days = Math.floor(hours / 24);
      const remainingHours = Math.round(hours % 24);
      return `${days}일 ${remainingHours}시간`;
    }
    return `${Math.round(hours)}시간`;
  };

  const formatSize = (gb: number | null) => {
    if (!gb) return '-';
    if (gb >= 1000) {
      return `${(gb / 1000).toFixed(1)} TB`;
    }
    return `${Math.round(gb)} GB`;
  };

  return (
    <Card className="mb-6">
      <div className="flex flex-wrap justify-around py-4 gap-6">
        <StatCard label="전체 파일" value={stats.total_files.toLocaleString()} />

        <StatCard
          label="공개 파일"
          value={stats.visible_files.toLocaleString()}
          subValue={`숨김: ${stats.hidden_files}`}
        />

        <StatCard
          label="총 재생시간"
          value={formatDuration(stats.total_duration_hours)}
        />

        <StatCard label="총 용량" value={formatSize(stats.total_size_gb)} />

        <StatCard
          label="프로젝트"
          value={Object.keys(stats.by_project).length}
          subValue={Object.keys(stats.by_project).slice(0, 3).join(', ')}
        />
      </div>
    </Card>
  );
}

export default CatalogStats;
