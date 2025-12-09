/**
 * Dashboard Page - 메인 대시보드 페이지
 * BLOCK_FRONTEND / FrontendAgent
 */

import { SyncStatusCard, DashboardStats, RecentActivityFeed } from '../components/dashboard';
import { useSyncStore } from '../store';
import { useDashboardStats, useTriggerSync, useSyncWebSocket } from '../hooks';
import { useNavigate } from 'react-router-dom';

export function Dashboard() {
  const navigate = useNavigate();

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
    recentLogs,
  } = useSyncStore();

  // API 데이터
  const { data: stats, isLoading: isStatsLoading } = useDashboardStats();
  const triggerSync = useTriggerSync();

  // 다음 동기화 예정 시간 (현재 시간 + 1시간으로 임시 계산)
  const getNextSync = (lastSync: Date | null) => {
    if (!lastSync) return null;
    const next = new Date(lastSync);
    next.setHours(next.getHours() + 1);
    return next;
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="text-gray-500 mt-1">NAS 및 Google Sheets 동기화 현황</p>
      </div>

      {/* Sync Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <SyncStatusCard
          source="nas"
          status={nasStatus}
          lastSync={nasLastSync}
          nextSync={getNextSync(nasLastSync)}
          itemCount={nasFilesCount || stats?.total_files || 0}
          progress={nasProgress}
          currentFile={nasCurrentFile}
          onTriggerSync={() => triggerSync.mutate('nas')}
          isTriggering={triggerSync.isPending && triggerSync.variables === 'nas'}
        />
        <SyncStatusCard
          source="sheets"
          status={sheetsStatus}
          lastSync={sheetsLastSync}
          nextSync={getNextSync(sheetsLastSync)}
          itemCount={sheetsRowsCount || stats?.total_hand_clips || 0}
          progress={sheetsProgress}
          onTriggerSync={() => triggerSync.mutate('sheets')}
          isTriggering={triggerSync.isPending && triggerSync.variables === 'sheets'}
        />
      </div>

      {/* Stats & Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <DashboardStats
            totalFiles={stats?.total_files || 0}
            totalCatalogs={stats?.total_catalogs || 0}
            totalClips={stats?.total_hand_clips || 0}
            storageGb={stats?.storage_usage?.total_size_gb || 0}
            byProject={stats?.by_project || {}}
            isLoading={isStatsLoading}
          />
        </div>
        <div>
          <RecentActivityFeed
            logs={recentLogs.length > 0 ? recentLogs : (stats?.recent_syncs || [])}
            maxItems={8}
            onViewAll={() => navigate('/logs')}
          />
        </div>
      </div>
    </div>
  );
}
