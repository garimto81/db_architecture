/**
 * SyncStatusCard Component - 동기화 상태 카드
 * BLOCK_FRONTEND / FrontendAgent
 */

import { Card, Badge, Button, ProgressBar } from '../common';
import type { SyncStatus, SyncSource } from '../../types';

interface SyncStatusCardProps {
  source: SyncSource;
  status: SyncStatus;
  lastSync: Date | null;
  nextSync: Date | null;
  itemCount: number;
  progress: number;
  currentFile?: string | null;
  onTriggerSync: () => void;
  isTriggering?: boolean;
}

const sourceConfig: Record<SyncSource, { icon: string; label: string; itemLabel: string }> = {
  nas: { icon: '📁', label: 'NAS 동기화', itemLabel: '파일 수' },
  sheets: { icon: '📊', label: 'Google Sheets 동기화', itemLabel: '행 수' },
};

function formatDate(date: Date | null): string {
  if (!date) return '-';
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
}

export function SyncStatusCard({
  source,
  status,
  lastSync,
  nextSync,
  itemCount,
  progress,
  currentFile,
  onTriggerSync,
  isTriggering = false,
}: SyncStatusCardProps) {
  const config = sourceConfig[source];
  const isRunning = status === 'running';

  return (
    <Card className="h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{config.icon}</span>
          <h3 className="text-lg font-semibold text-gray-900">{config.label}</h3>
        </div>
        <Badge status={status} />
      </div>

      {/* Stats */}
      <div className="space-y-3 mb-4">
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">마지막 동기화</span>
          <span className="text-gray-900 font-medium">{formatDate(lastSync)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">다음 예정</span>
          <span className="text-gray-900 font-medium">{formatDate(nextSync)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">{config.itemLabel}</span>
          <span className="text-gray-900 font-medium">{itemCount.toLocaleString()}</span>
        </div>
      </div>

      {/* Progress (when running) */}
      {isRunning && (
        <div className="mb-4">
          <ProgressBar progress={progress} showLabel size="md" />
          {currentFile && (
            <p className="mt-1 text-xs text-gray-500 truncate" title={currentFile}>
              {currentFile}
            </p>
          )}
        </div>
      )}

      {/* Action */}
      <Button
        onClick={onTriggerSync}
        disabled={isRunning || isTriggering}
        loading={isTriggering}
        icon="🔄"
        className="w-full"
        size="sm"
      >
        지금 동기화
      </Button>
    </Card>
  );
}
