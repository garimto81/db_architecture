/**
 * Header Component - 상단 헤더 네비게이션
 * BLOCK_FRONTEND / FrontendAgent
 */

import { Link, useLocation } from 'react-router-dom';
import { useSyncStore } from '../../store';

const navigation = [
  { name: 'Dashboard', path: '/' },
  { name: 'Sync', path: '/sync' },
  { name: 'Logs', path: '/logs' },
];

export function Header() {
  const location = useLocation();
  const { wsConnected, notifications } = useSyncStore();
  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Title */}
          <div className="flex items-center gap-3">
            <span className="text-2xl">🎰</span>
            <h1 className="text-xl font-bold text-gray-900">
              {import.meta.env.VITE_APP_TITLE || 'GGP Poker Video Catalog'}
            </h1>
          </div>

          {/* Navigation */}
          <nav className="flex items-center gap-1">
            {navigation.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-brand-primary text-white'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                >
                  {item.name}
                </Link>
              );
            })}
          </nav>

          {/* Status Indicators */}
          <div className="flex items-center gap-4">
            {/* WebSocket Status */}
            <div className="flex items-center gap-2 text-sm">
              <span
                className={`w-2 h-2 rounded-full ${
                  wsConnected ? 'bg-green-500' : 'bg-red-500'
                }`}
              />
              <span className="text-gray-500">{wsConnected ? 'Connected' : 'Disconnected'}</span>
            </div>

            {/* Notifications */}
            {unreadCount > 0 && (
              <div className="relative">
                <span className="text-xl">🔔</span>
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                  {unreadCount}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
