/**
 * RecentActivityFeed Component - 최근 활동 피드
 * BLOCK_FRONTEND / FrontendAgent
 */

import { Card } from '../common';
import type { SyncLogEntry } from '../../types';

interface ActivityItemProps {
  log: SyncLogEntry;
}

function ActivityItem({ log }: ActivityItemProps) {
  const getIcon = () => {
    switch (log.type) {
      case 'start':
        return '▶️';
      case 'complete':
        return '✅';
      case 'error':
        return '❌';
      default:
        return '●';
    }
  };

  const getStatusClass = () => {
    switch (log.type) {
      case 'complete':
        return 'text-green-600';
      case 'error':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const getDetails = () => {
    if (!log.details) return null;

    if (log.type === 'complete') {
      const { files_added = 0, files_updated = 0, errors = 0 } = log.details as {
        files_added?: number;
        files_updated?: number;
        errors?: number;
      };
      return `+${files_added} 추가, ${files_updated} 업데이트, ${errors} 에러`;
    }

    return null;
  };

  return (
    <div className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
      <span className="text-lg">{getIcon()}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className={`text-sm font-medium ${getStatusClass()}`}>{log.message}</span>
          <span className="text-xs text-gray-400 ml-2 whitespace-nowrap">
            {formatTime(log.timestamp)}
          </span>
        </div>
        {getDetails() && <p className="text-xs text-gray-500 mt-0.5">{getDetails()}</p>}
      </div>
    </div>
  );
}

interface RecentActivityFeedProps {
  logs: SyncLogEntry[];
  maxItems?: number;
  onViewAll?: () => void;
}

export function RecentActivityFeed({ logs, maxItems = 10, onViewAll }: RecentActivityFeedProps) {
  const displayLogs = logs.slice(0, maxItems);

  return (
    <Card
      title="🕐 최근 활동"
      action={
        onViewAll && (
          <button onClick={onViewAll} className="text-sm text-brand-primary hover:underline">
            모두 보기
          </button>
        )
      }
    >
      {displayLogs.length === 0 ? (
        <p className="text-center text-gray-500 py-4">최근 활동이 없습니다.</p>
      ) : (
        <div className="max-h-80 overflow-y-auto">
          {displayLogs.map((log) => (
            <ActivityItem key={log.id} log={log} />
          ))}
        </div>
      )}
    </Card>
  );
}
