/**
 * DashboardStats Component - 대시보드 통계 카드
 * BLOCK_FRONTEND / FrontendAgent
 */

import { Card } from '../common';

interface StatCardProps {
  value: number | string;
  label: string;
  icon: string;
}

function StatCard({ value, label, icon }: StatCardProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
      <div className="text-3xl mb-1">{icon}</div>
      <div className="text-2xl font-bold text-gray-900">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      <div className="text-sm text-gray-500">{label}</div>
    </div>
  );
}

interface ProjectBarProps {
  code: string;
  count: number;
  maxCount: number;
}

function ProjectBar({ code, count, maxCount }: ProjectBarProps) {
  const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;

  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-sm font-medium text-gray-700">{code}</span>
      <div className="flex-1 bg-gray-200 rounded-full h-4">
        <div
          className="bg-brand-primary h-4 rounded-full transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="w-16 text-sm text-gray-600 text-right">{count.toLocaleString()}</span>
    </div>
  );
}

interface DashboardStatsProps {
  totalFiles: number;
  totalCatalogs: number;
  totalClips: number;
  storageGb: number;
  byProject: Record<string, number>;
  isLoading?: boolean;
}

export function DashboardStats({
  totalFiles,
  totalCatalogs,
  totalClips,
  storageGb,
  byProject,
  isLoading = false,
}: DashboardStatsProps) {
  // 프로젝트별 데이터 정렬 (파일 수 내림차순)
  const sortedProjects = Object.entries(byProject)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 7); // 상위 7개만 표시

  const maxCount = sortedProjects.length > 0 ? sortedProjects[0][1] : 0;

  if (isLoading) {
    return (
      <Card title="📊 전체 통계" className="animate-pulse">
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gray-200 rounded-lg h-24" />
          ))}
        </div>
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="bg-gray-200 rounded h-6" />
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card title="📊 전체 통계">
      {/* Stat Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard value={totalFiles} label="파일" icon="📁" />
        <StatCard value={totalCatalogs} label="카탈로그" icon="📋" />
        <StatCard value={totalClips} label="클립" icon="🎬" />
        <StatCard value={`${storageGb.toFixed(1)}TB`} label="저장공간" icon="💾" />
      </div>

      {/* Project Distribution */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-3">프로젝트별 분포</h4>
        <div className="space-y-2">
          {sortedProjects.map(([code, count]) => (
            <ProjectBar key={code} code={code} count={count} maxCount={maxCount} />
          ))}
        </div>
      </div>
    </Card>
  );
}
