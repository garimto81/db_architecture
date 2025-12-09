/**
 * Toast Component - 알림 토스트 시스템
 * BLOCK_FRONTEND / FrontendAgent
 *
 * Zustand store의 notifications를 구독하여 토스트를 표시합니다.
 */

import { useEffect, useState } from 'react';
import { useSyncStore, type Notification } from '../../store';

interface ToastItemProps {
  notification: Notification;
  onDismiss: (id: string) => void;
}

const typeConfig: Record<Notification['type'], { icon: string; bgClass: string; borderClass: string }> = {
  info: {
    icon: 'ℹ️',
    bgClass: 'bg-blue-50',
    borderClass: 'border-blue-200',
  },
  success: {
    icon: '✅',
    bgClass: 'bg-green-50',
    borderClass: 'border-green-200',
  },
  warning: {
    icon: '⚠️',
    bgClass: 'bg-yellow-50',
    borderClass: 'border-yellow-200',
  },
  error: {
    icon: '❌',
    bgClass: 'bg-red-50',
    borderClass: 'border-red-200',
  },
};

function ToastItem({ notification, onDismiss }: ToastItemProps) {
  const [isExiting, setIsExiting] = useState(false);
  const config = typeConfig[notification.type];

  // 자동 dismiss (5초 후)
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsExiting(true);
      setTimeout(() => onDismiss(notification.id), 300);
    }, 5000);

    return () => clearTimeout(timer);
  }, [notification.id, onDismiss]);

  const handleDismiss = () => {
    setIsExiting(true);
    setTimeout(() => onDismiss(notification.id), 300);
  };

  return (
    <div
      className={`
        ${config.bgClass} ${config.borderClass}
        border rounded-lg shadow-lg p-4 mb-2 max-w-sm
        transform transition-all duration-300
        ${isExiting ? 'opacity-0 translate-x-full' : 'opacity-100 translate-x-0'}
      `}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <span className="text-xl flex-shrink-0">{config.icon}</span>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-900">{notification.title}</p>
          <p className="text-sm text-gray-600 mt-0.5">{notification.message}</p>
          <p className="text-xs text-gray-400 mt-1">
            {notification.timestamp.toLocaleTimeString('ko-KR')}
          </p>
        </div>
        <button
          onClick={handleDismiss}
          className="text-gray-400 hover:text-gray-600 flex-shrink-0"
          aria-label="닫기"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

export function ToastContainer() {
  const { notifications, markNotificationRead } = useSyncStore();

  // 읽지 않은 알림만 표시 (최대 5개)
  const unreadNotifications = notifications
    .filter((n) => !n.read)
    .slice(0, 5);

  if (unreadNotifications.length === 0) {
    return null;
  }

  return (
    <div
      className="fixed top-20 right-4 z-50"
      aria-live="polite"
      aria-label="알림"
    >
      {unreadNotifications.map((notification) => (
        <ToastItem
          key={notification.id}
          notification={notification}
          onDismiss={markNotificationRead}
        />
      ))}
    </div>
  );
}
