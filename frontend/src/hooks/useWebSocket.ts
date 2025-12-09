/**
 * WebSocket Hook - 실시간 동기화 이벤트 처리
 * BLOCK_FRONTEND / FrontendAgent
 */

import { useEffect, useCallback } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { getWsUrl } from '../services/api';
import { useSyncStore } from '../store';
import type {
  WsMessage,
  SyncStartPayload,
  SyncProgressPayload,
  SyncCompletePayload,
  SyncErrorPayload,
} from '../types';

const WS_SYNC_URL = getWsUrl('/ws/sync');

export function useSyncWebSocket() {
  const {
    setNasStatus,
    setNasProgress,
    setNasComplete,
    setSheetsStatus,
    setSheetsProgress,
    setSheetsComplete,
    addLog,
    addNotification,
    setWsConnected,
  } = useSyncStore();

  const { lastMessage, readyState } = useWebSocket(WS_SYNC_URL, {
    shouldReconnect: () => true,
    reconnectAttempts: 10,
    reconnectInterval: 3000,
    onOpen: () => {
      console.log('[WS] Connected to sync WebSocket');
      setWsConnected(true);
    },
    onClose: () => {
      console.log('[WS] Disconnected from sync WebSocket');
      setWsConnected(false);
    },
    onError: (event) => {
      console.error('[WS] WebSocket error:', event);
    },
  });

  // WebSocket 메시지 처리
  const handleMessage = useCallback(
    (message: WsMessage) => {
      const { type, timestamp, payload } = message;

      switch (type) {
        case 'sync_start': {
          const data = payload as SyncStartPayload;
          if (data.source === 'nas') {
            setNasStatus('running');
            setNasProgress(0);
          } else {
            setSheetsStatus('running');
            setSheetsProgress(0);
          }
          addLog({
            id: data.sync_id,
            timestamp,
            source: data.source,
            type: 'start',
            message: `${data.source.toUpperCase()} 동기화 시작 (${data.triggered_by})`,
          });
          break;
        }

        case 'sync_progress': {
          const data = payload as SyncProgressPayload;
          if (data.source === 'nas') {
            setNasProgress(data.percentage, data.current_file);
          } else {
            setSheetsProgress(data.percentage);
          }
          break;
        }

        case 'sync_complete': {
          const data = payload as SyncCompletePayload;
          if (data.source === 'nas') {
            setNasComplete(data.files_processed);
          } else {
            setSheetsComplete(data.files_processed);
          }
          addLog({
            id: data.sync_id,
            timestamp,
            source: data.source,
            type: 'complete',
            message: `${data.source.toUpperCase()} 동기화 완료`,
            details: {
              duration_ms: data.duration_ms,
              files_processed: data.files_processed,
              files_added: data.files_added,
              files_updated: data.files_updated,
              errors: data.errors,
            },
          });
          addNotification({
            type: 'success',
            title: '동기화 완료',
            message: `${data.source.toUpperCase()}: ${data.files_added}개 추가, ${data.files_updated}개 업데이트`,
          });
          break;
        }

        case 'sync_error': {
          const data = payload as SyncErrorPayload;
          if (data.source === 'nas') {
            setNasStatus('error');
          } else {
            setSheetsStatus('error');
          }
          addLog({
            id: data.sync_id,
            timestamp,
            source: data.source,
            type: 'error',
            message: `${data.source.toUpperCase()} 동기화 실패: ${data.message}`,
            details: { error_code: data.error_code },
          });
          addNotification({
            type: 'error',
            title: '동기화 실패',
            message: `${data.source.toUpperCase()}: ${data.message}`,
          });
          break;
        }

        case 'file_found':
        case 'sheet_updated':
          // 개별 이벤트는 필요시 처리
          break;

        default:
          console.warn('[WS] Unknown message type:', type);
      }
    },
    [
      setNasStatus,
      setNasProgress,
      setNasComplete,
      setSheetsStatus,
      setSheetsProgress,
      setSheetsComplete,
      addLog,
      addNotification,
    ]
  );

  // 새 메시지 수신 시 처리
  useEffect(() => {
    if (lastMessage !== null) {
      try {
        const data = JSON.parse(lastMessage.data) as WsMessage;
        handleMessage(data);
      } catch (error) {
        console.error('[WS] Failed to parse message:', error);
      }
    }
  }, [lastMessage, handleMessage]);

  return {
    isConnected: readyState === ReadyState.OPEN,
    readyState,
  };
}
