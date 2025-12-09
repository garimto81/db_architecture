/**
 * Badge Component - 상태 표시 배지
 * BLOCK_FRONTEND / FrontendAgent
 */

import type { SyncStatus } from '../../types';

interface BadgeProps {
  status: SyncStatus;
  label?: string;
}

const statusConfig: Record<SyncStatus, { class: string; defaultLabel: string }> = {
  idle: { class: 'badge-idle', defaultLabel: 'Idle' },
  running: { class: 'badge-running', defaultLabel: 'Running' },
  error: { class: 'badge-error', defaultLabel: 'Error' },
};

export function Badge({ status, label }: BadgeProps) {
  const config = statusConfig[status];

  return (
    <span className={`badge ${config.class}`}>
      {status === 'running' && (
        <span className="w-2 h-2 mr-1.5 bg-blue-500 rounded-full animate-pulse" />
      )}
      {status === 'error' && <span className="mr-1">●</span>}
      {label || config.defaultLabel}
    </span>
  );
}
