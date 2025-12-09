/**
 * Sync Store - Zustand 기반 동기화 상태 관리
 * BLOCK_FRONTEND / FrontendAgent
 */

import { create } from 'zustand';
import type { SyncStatus, SyncLogEntry, SyncSource } from '../types';

// 알림 타입
export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
}

interface SyncState {
  // NAS 상태
  nasStatus: SyncStatus;
  nasLastSync: Date | null;
  nasProgress: number;
  nasFilesCount: number;
  nasCurrentFile: string | null;

  // Sheets 상태
  sheetsStatus: SyncStatus;
  sheetsLastSync: Date | null;
  sheetsProgress: number;
  sheetsRowsCount: number;

  // 로그
  recentLogs: SyncLogEntry[];

  // 알림
  notifications: Notification[];

  // WebSocket 연결 상태
  wsConnected: boolean;

  // 액션: NAS 상태 업데이트
  setNasStatus: (status: SyncStatus) => void;
  setNasProgress: (progress: number, currentFile?: string) => void;
  setNasComplete: (filesCount: number) => void;

  // 액션: Sheets 상태 업데이트
  setSheetsStatus: (status: SyncStatus) => void;
  setSheetsProgress: (progress: number) => void;
  setSheetsComplete: (rowsCount: number) => void;

  // 액션: 로그
  addLog: (log: SyncLogEntry) => void;
  clearLogs: () => void;

  // 액션: 알림
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  markNotificationRead: (id: string) => void;
  clearNotifications: () => void;

  // 액션: WebSocket
  setWsConnected: (connected: boolean) => void;

  // 액션: 동기화 시작
  startSync: (source: SyncSource) => void;
}

export const useSyncStore = create<SyncState>((set) => ({
  // 초기 상태: NAS
  nasStatus: 'idle',
  nasLastSync: null,
  nasProgress: 0,
  nasFilesCount: 0,
  nasCurrentFile: null,

  // 초기 상태: Sheets
  sheetsStatus: 'idle',
  sheetsLastSync: null,
  sheetsProgress: 0,
  sheetsRowsCount: 0,

  // 초기 상태: 로그 & 알림
  recentLogs: [],
  notifications: [],
  wsConnected: false,

  // NAS 액션
  setNasStatus: (status) => set({ nasStatus: status }),

  setNasProgress: (progress, currentFile) =>
    set({ nasProgress: progress, nasCurrentFile: currentFile ?? null }),

  setNasComplete: (filesCount) =>
    set({
      nasStatus: 'idle',
      nasProgress: 100,
      nasFilesCount: filesCount,
      nasLastSync: new Date(),
      nasCurrentFile: null,
    }),

  // Sheets 액션
  setSheetsStatus: (status) => set({ sheetsStatus: status }),

  setSheetsProgress: (progress) => set({ sheetsProgress: progress }),

  setSheetsComplete: (rowsCount) =>
    set({
      sheetsStatus: 'idle',
      sheetsProgress: 100,
      sheetsRowsCount: rowsCount,
      sheetsLastSync: new Date(),
    }),

  // 로그 액션
  addLog: (log) =>
    set((state) => ({
      recentLogs: [log, ...state.recentLogs].slice(0, 50), // 최대 50개 유지
    })),

  clearLogs: () => set({ recentLogs: [] }),

  // 알림 액션
  addNotification: (notification) =>
    set((state) => ({
      notifications: [
        {
          ...notification,
          id: crypto.randomUUID(),
          timestamp: new Date(),
          read: false,
        },
        ...state.notifications,
      ].slice(0, 20), // 최대 20개 유지
    })),

  markNotificationRead: (id) =>
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
    })),

  clearNotifications: () => set({ notifications: [] }),

  // WebSocket 액션
  setWsConnected: (connected) => set({ wsConnected: connected }),

  // 동기화 시작 액션
  startSync: (source) => {
    if (source === 'nas') {
      set({ nasStatus: 'running', nasProgress: 0, nasCurrentFile: null });
    } else {
      set({ sheetsStatus: 'running', sheetsProgress: 0 });
    }
  },
}));
