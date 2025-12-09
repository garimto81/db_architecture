# LLD: Frontend Monitoring Dashboard

> **버전**: 1.3.0 | **기준 PRD**: PRD_BLOCK_AGENT_SYSTEM v1.1.0 | **작성일**: 2025-12-09

---

## 1. 개요

### 1.1 목적

본 문서는 NAS 폴더와 Google Sheets 데이터를 실시간 모니터링하고 동기화 상태를 시각화하는 Frontend Dashboard의 Low-Level Design을 정의합니다.

### 1.2 범위

| 포함 | 제외 |
|------|------|
| NAS 동기화 상태 모니터링 | 비디오 스트리밍/재생 |
| Google Sheets 동기화 상태 | 사용자 인증/권한 |
| 실시간 WebSocket 업데이트 | 영상 편집 기능 |
| 수동 동기화 트리거 | 복잡한 분석 대시보드 |
| 동기화 히스토리/로그 | |

### 1.3 담당 Block/Agent

**전담 에이전트**: FrontendAgent

| 항목 | 값 |
|------|-----|
| 블럭 ID | BLOCK_FRONTEND |
| 언어 | TypeScript (React) |
| 파일 수 한도 | 40개 |
| 토큰 한도 | 45K |
| 통신 방식 | REST API, WebSocket |

### 1.4 블럭 규칙 (.block_rules)

```yaml
# frontend/.block_rules
block_id: BLOCK_FRONTEND
agent: FrontendAgent
language: typescript

scope:
  allowed_paths:
    - "frontend/**"
    - "frontend/src/**/*.tsx"
    - "frontend/src/**/*.ts"
    - "frontend/src/**/*.css"
  forbidden_paths:
    - "backend/**"
    - "blocks/**"
    - "src/agents/**"
    - "*.py"
    - "*.sql"
    - "docker/**"

limits:
  max_files: 40
  max_tokens: 45000

dependencies:
  - BLOCK_SYNC          # 동기화 이벤트 구독 (WebSocket 통해)

communication:
  allowed:
    - protocol: http
      target: "backend/api/*"
    - protocol: websocket
      target: "backend/ws/*"
  forbidden:
    - protocol: direct
      target: "database"
    - protocol: import
      target: "python_modules"

capabilities:
  - render_dashboard      # 대시보드 UI 렌더링
  - handle_websocket      # WebSocket 이벤트 처리
  - update_sync_status    # 동기화 상태 UI 업데이트
  - show_notification     # 알림 토스트 표시
  - fetch_stats           # REST API로 통계 조회
  - trigger_sync          # 수동 동기화 트리거
```

### 1.5 블럭 격리 원칙

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BLOCK_FRONTEND 격리 경계                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ✅ 허용된 통신 경로:                                                │
│  ┌──────────────┐     HTTP/WS      ┌──────────────┐                │
│  │  Frontend    │ ◀══════════════▶ │  Backend API │                │
│  │  (React)     │                   │  (FastAPI)   │                │
│  └──────────────┘                   └──────────────┘                │
│                                                                      │
│  ❌ 금지된 통신 경로:                                                │
│  ┌──────────────┐                   ┌──────────────┐                │
│  │  Frontend    │ ───── ✗ ────────▶│  Database    │  직접 DB 접근  │
│  │  (React)     │ ───── ✗ ────────▶│  Python 코드 │  import 금지   │
│  │              │ ───── ✗ ────────▶│  다른 블럭   │  경로 접근 금지│
│  └──────────────┘                   └──────────────┘                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.6 폴더 구조 (블럭 경계)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BLOCK_FRONTEND (신규)                         │
├─────────────────────────────────────────────────────────────────────┤
│  책임: GUI 모니터링 대시보드 렌더링 및 실시간 데이터 표시            │
│                                                                      │
│  폴더 구조:                                                          │
│  /frontend/                                                          │
│  ├── src/                                                            │
│  │   ├── components/                                                 │
│  │   │   ├── dashboard/         # 대시보드 컴포넌트                  │
│  │   │   ├── sync/              # 동기화 상태 컴포넌트               │
│  │   │   └── common/            # 공통 UI 컴포넌트                   │
│  │   ├── hooks/                 # Custom React Hooks                 │
│  │   │   ├── useWebSocket.ts    # WebSocket 연결                     │
│  │   │   └── useSyncStatus.ts   # 동기화 상태 관리                   │
│  │   ├── services/              # API 클라이언트                      │
│  │   ├── store/                 # 상태 관리 (Zustand)                │
│  │   └── types/                 # TypeScript 타입 정의               │
│  └── tests/                                                          │
│                                                                      │
│  의존: BLOCK_SYNC (동기화 데이터), Backend API (REST + WebSocket)    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 기술 스택 결정

### 2.1 Make vs Buy 분석

| 옵션 | Stars | 라이선스 | 장점 | 단점 | 추천 |
|------|-------|----------|------|------|------|
| **직접 개발** | - | - | 완전 커스터마이징 | 개발 시간 필요 | ✅ |
| React-Admin | 25k+ | MIT | 완성된 Admin UI | 과도한 기능 | |
| Refine | 15k+ | MIT | Headless, 유연 | 러닝 커브 | |
| AdminJS | 7k+ | MIT | Node 특화 | Python 백엔드 비호환 | |

**결정**: 직접 개발 (React + TypeScript)
- 기존 db_architecture 프로젝트에 맞춤화 필요
- 간단한 모니터링 기능만 필요 (Admin 기능 불필요)
- Backend API가 이미 FastAPI로 구현되어 있음

### 2.2 기술 스택

| 계층 | 기술 | 버전 | 선택 이유 |
|------|------|------|----------|
| **Framework** | React | 18.x | 생태계, 커뮤니티 |
| **Language** | TypeScript | 5.x | 타입 안정성 |
| **Build** | Vite | 5.x | 빠른 HMR |
| **UI Library** | shadcn/ui | latest | Tailwind 기반, 커스터마이징 용이 |
| **State** | Zustand | 4.x | 경량, 간단한 API |
| **Data Fetching** | TanStack Query | 5.x | 서버 상태 관리 |
| **WebSocket** | react-use-websocket | 4.x | React 통합 |
| **Charts** | Recharts | 2.x | React 친화적 |
| **Styling** | Tailwind CSS | 3.x | 유틸리티 CSS |

---

## 3. 시스템 아키텍처

### 3.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND DASHBOARD                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                         React Application                           │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │    │
│  │  │  Dashboard  │  │  SyncPanel  │  │  LogViewer  │                 │    │
│  │  │  Component  │  │  Component  │  │  Component  │                 │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │    │
│  │         │                │                │                         │    │
│  │         └────────────────┼────────────────┘                         │    │
│  │                          ▼                                          │    │
│  │  ┌───────────────────────────────────────────────────────────────┐ │    │
│  │  │                    Zustand Store                               │ │    │
│  │  │  syncStatus │ nasFiles │ sheetData │ logs │ notifications     │ │    │
│  │  └───────────────────────────────────────────────────────────────┘ │    │
│  │                          │                                          │    │
│  │         ┌────────────────┼────────────────┐                         │    │
│  │         ▼                ▼                ▼                         │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │    │
│  │  │ REST Client │  │ WebSocket   │  │ TanStack    │                 │    │
│  │  │ (Axios)     │  │ Client      │  │ Query       │                 │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │    │
│  │         │                │                │                         │    │
│  └─────────┼────────────────┼────────────────┼─────────────────────────┘    │
│            │                │                │                              │
└────────────┼────────────────┼────────────────┼──────────────────────────────┘
             │                │                │
             ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND (FastAPI)                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ /api/sync   │  │ /api/stats  │  │ /api/logs   │  │ /ws/sync    │        │
│  │  status     │  │  dashboard  │  │  history    │  │  events     │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │                │
│         └────────────────┼────────────────┼────────────────┘                │
│                          ▼                                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                       Sync Services                                    │ │
│  │  NAS Scanner │ Sheets Parser │ Scheduler │ Event Emitter              │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 데이터 흐름

```
1. 초기 로딩:
   Dashboard → REST API → 현재 상태 조회 → Store 업데이트 → UI 렌더링

2. 실시간 업데이트:
   Backend Event → WebSocket → Store 업데이트 → UI 자동 렌더링

3. 수동 동기화:
   버튼 클릭 → REST API (POST) → 작업 시작 → WebSocket 진행률 → 완료 알림
```

---

## 4. Backend API 확장

### 4.1 신규 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/sync/status` | 현재 동기화 상태 |
| GET | `/api/sync/history` | 동기화 히스토리 (페이지네이션) |
| POST | `/api/sync/trigger/{source}` | 수동 동기화 트리거 |
| GET | `/api/dashboard/stats` | 대시보드 통계 |
| GET | `/api/dashboard/health` | 시스템 헬스체크 |
| WS | `/ws/sync` | 실시간 동기화 이벤트 |

### 4.2 WebSocket 이벤트 스키마

```typescript
// WebSocket 메시지 타입
interface WsMessage {
  type: 'sync_start' | 'sync_progress' | 'sync_complete' | 'sync_error' | 'file_found' | 'sheet_updated';
  timestamp: string;
  payload: SyncStartPayload | SyncProgressPayload | SyncCompletePayload | SyncErrorPayload;
}

interface SyncStartPayload {
  sync_id: string;
  source: 'nas' | 'sheets';
  triggered_by: 'scheduler' | 'manual';
}

interface SyncProgressPayload {
  sync_id: string;
  source: 'nas' | 'sheets';
  current: number;
  total: number;
  current_file?: string;
  percentage: number;
}

interface SyncCompletePayload {
  sync_id: string;
  source: 'nas' | 'sheets';
  duration_ms: number;
  files_processed: number;
  files_added: number;
  files_updated: number;
  errors: number;
}

interface SyncErrorPayload {
  sync_id: string;
  source: 'nas' | 'sheets';
  error_code: string;
  message: string;
}
```

### 4.3 REST API 응답 스키마

```typescript
// GET /api/sync/status
interface SyncStatusResponse {
  nas: {
    last_sync: string;      // ISO datetime
    status: 'idle' | 'running' | 'error';
    files_count: number;
    next_scheduled: string;
  };
  sheets: {
    last_sync: string;
    status: 'idle' | 'running' | 'error';
    rows_count: number;
    next_scheduled: string;
  };
  scheduler: {
    is_running: boolean;
    jobs: SchedulerJob[];
  };
}

// GET /api/dashboard/stats
interface DashboardStatsResponse {
  total_files: number;
  total_hand_clips: number;
  by_project: Record<string, number>;
  by_year: Record<string, number>;
  recent_syncs: SyncLogEntry[];
  storage_usage: {
    total_size_gb: number;
    by_project: Record<string, number>;
  };
}
```

---

## 5. Frontend 컴포넌트 설계

### 5.1 페이지 구조

```
/                           # Dashboard (메인)
├── Overview               # 전체 통계 카드
├── SyncStatus             # NAS/Sheets 동기화 상태
├── RecentActivity         # 최근 활동 로그
└── QuickActions           # 수동 동기화 버튼

/sync                      # 동기화 상세
├── NasSyncPanel           # NAS 동기화 상태/제어
├── SheetsSyncPanel        # Sheets 동기화 상태/제어
└── SyncHistory            # 동기화 히스토리 테이블

/logs                      # 로그 뷰어
├── SyncLogList            # 동기화 로그 목록
└── LogDetail              # 로그 상세 모달
```

### 5.2 핵심 컴포넌트

#### 5.2.1 SyncStatusCard

```tsx
interface SyncStatusCardProps {
  source: 'nas' | 'sheets';
  status: 'idle' | 'running' | 'error';
  lastSync: Date;
  nextSync: Date;
  itemCount: number;
  onTriggerSync: () => void;
}

// UI 목업
┌─────────────────────────────────────────────────┐
│  📁 NAS 동기화                    ● Running     │
│  ─────────────────────────────────────────────  │
│  마지막 동기화: 2025-12-09 14:00:00            │
│  다음 예정: 2025-12-09 15:00:00                 │
│  파일 수: 1,856                                 │
│  ─────────────────────────────────────────────  │
│  [진행률: ████████░░░░░░ 65%]                   │
│                                                 │
│                              [🔄 지금 동기화]   │
└─────────────────────────────────────────────────┘
```

#### 5.2.2 DashboardStats

```tsx
interface DashboardStatsProps {
  totalFiles: number;
  totalClips: number;
  byProject: Record<string, number>;
  storageGb: number;
}

// UI 목업
┌─────────────────────────────────────────────────────────────────────┐
│  📊 전체 통계                                                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │  1,856   │  │   815    │  │  117     │  │  2.4TB   │           │
│  │  파일    │  │ 카탈로그  │  │ 그룹     │  │ 저장공간  │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
│                                                                      │
│  프로젝트별 분포                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ WSOP     ████████████████████████████████████░░░  1,764     │   │
│  │ PAD      ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     44     │   │
│  │ GOG      ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     24     │   │
│  │ GGMILLIONS █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     13     │   │
│  │ MPP      █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     11     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 5.2.3 RecentActivityFeed

```tsx
// UI 목업
┌─────────────────────────────────────────────────────────────────────┐
│  🕐 최근 활동                                          [모두 보기]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ● 14:00:32  NAS 동기화 완료         +12 파일, 0 에러     ✅        │
│  ● 14:00:01  NAS 동기화 시작         scheduler 트리거               │
│  ● 13:00:45  Sheets 동기화 완료      +5 행, 0 에러        ✅        │
│  ● 13:00:02  Sheets 동기화 시작      scheduler 트리거               │
│  ● 12:00:38  NAS 동기화 완료         +0 파일, 0 에러      ✅        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 Zustand Store 설계

```typescript
// store/syncStore.ts
interface SyncState {
  // NAS 상태
  nasStatus: 'idle' | 'running' | 'error';
  nasLastSync: Date | null;
  nasProgress: number;
  nasFilesCount: number;

  // Sheets 상태
  sheetsStatus: 'idle' | 'running' | 'error';
  sheetsLastSync: Date | null;
  sheetsProgress: number;
  sheetsRowsCount: number;

  // 로그
  recentLogs: SyncLogEntry[];

  // 알림
  notifications: Notification[];

  // 액션
  setNasStatus: (status: SyncState['nasStatus']) => void;
  setSheetsStatus: (status: SyncState['sheetsStatus']) => void;
  addLog: (log: SyncLogEntry) => void;
  addNotification: (notification: Notification) => void;
  clearNotifications: () => void;
}

// store/dashboardStore.ts
interface DashboardState {
  stats: DashboardStats | null;
  isLoading: boolean;
  error: string | null;

  fetchStats: () => Promise<void>;
}
```

### 5.4 Custom Hooks

```typescript
// hooks/useWebSocket.ts
function useSyncWebSocket() {
  const { sendMessage, lastMessage, readyState } = useWebSocket(
    `${WS_BASE_URL}/ws/sync`,
    {
      shouldReconnect: () => true,
      reconnectAttempts: 10,
      reconnectInterval: 3000,
    }
  );

  // 메시지 파싱 및 스토어 업데이트
  useEffect(() => {
    if (lastMessage) {
      const data = JSON.parse(lastMessage.data) as WsMessage;
      handleWsMessage(data);
    }
  }, [lastMessage]);

  return { isConnected: readyState === ReadyState.OPEN };
}

// hooks/useSyncStatus.ts
function useSyncStatus() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['syncStatus'],
    queryFn: fetchSyncStatus,
    refetchInterval: 30000, // 30초마다 폴링 (WebSocket 백업)
  });

  const triggerSync = useMutation({
    mutationFn: (source: 'nas' | 'sheets') => triggerSyncApi(source),
    onSuccess: () => refetch(),
  });

  return { status: data, isLoading, triggerSync };
}
```

---

## 6. 폴더 구조

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── components/
│   │   ├── dashboard/
│   │   │   ├── DashboardStats.tsx
│   │   │   ├── SyncStatusCard.tsx
│   │   │   ├── RecentActivityFeed.tsx
│   │   │   └── QuickActions.tsx
│   │   ├── sync/
│   │   │   ├── NasSyncPanel.tsx
│   │   │   ├── SheetsSyncPanel.tsx
│   │   │   ├── SyncProgress.tsx
│   │   │   └── SyncHistory.tsx
│   │   ├── logs/
│   │   │   ├── LogList.tsx
│   │   │   └── LogDetail.tsx
│   │   ├── common/
│   │   │   ├── Card.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Button.tsx
│   │   │   ├── ProgressBar.tsx
│   │   │   └── Notification.tsx
│   │   └── layout/
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── Layout.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useSyncStatus.ts
│   │   └── useDashboardStats.ts
│   ├── services/
│   │   ├── api.ts            # Axios 인스턴스
│   │   ├── syncApi.ts        # 동기화 API
│   │   └── dashboardApi.ts   # 대시보드 API
│   ├── store/
│   │   ├── syncStore.ts
│   │   └── dashboardStore.ts
│   ├── types/
│   │   ├── sync.ts
│   │   ├── dashboard.ts
│   │   └── api.ts
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Sync.tsx
│   │   └── Logs.tsx
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── tests/
│   ├── components/
│   └── hooks/
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── vite.config.ts
└── .env.example
```

---

## 7. Backend 확장 구현

### 7.1 WebSocket 라우터 (`backend/src/api/ws.py`)

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@router.websocket("/ws/sync")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, receive commands
            data = await websocket.receive_text()
            # Handle incoming commands if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# 다른 서비스에서 호출할 broadcast 함수
async def broadcast_sync_event(event_type: str, payload: dict):
    message = {
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "payload": payload
    }
    await manager.broadcast(message)
```

### 7.2 Dashboard API (`backend/src/api/dashboard.py`)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.database import get_db
from src.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """대시보드 통계 조회"""
    service = DashboardService(db)
    return service.get_stats()

@router.get("/health")
def get_system_health(db: Session = Depends(get_db)):
    """시스템 헬스체크"""
    service = DashboardService(db)
    return service.get_health()
```

---

## 8. 구현 일정

### Phase 1: 기반 구축 (2일)

| 태스크 | 설명 | 산출물 |
|--------|------|--------|
| T1.1 | Frontend 프로젝트 초기화 | Vite + React + TypeScript |
| T1.2 | UI 라이브러리 설정 | shadcn/ui + Tailwind |
| T1.3 | 라우팅 설정 | React Router |
| T1.4 | 상태 관리 설정 | Zustand stores |

### Phase 2: Backend API 확장 (2일)

| 태스크 | 설명 | 산출물 |
|--------|------|--------|
| T2.1 | WebSocket 엔드포인트 | `/ws/sync` |
| T2.2 | Dashboard API | `/api/dashboard/*` |
| T2.3 | Sync trigger API | `/api/sync/trigger` |
| T2.4 | Event emitter 통합 | Scheduler → WebSocket |

### Phase 3: Dashboard 컴포넌트 (3일)

| 태스크 | 설명 | 산출물 |
|--------|------|--------|
| T3.1 | DashboardStats 구현 | 통계 카드 |
| T3.2 | SyncStatusCard 구현 | 동기화 상태 카드 |
| T3.3 | RecentActivityFeed 구현 | 활동 로그 |
| T3.4 | WebSocket 훅 구현 | 실시간 업데이트 |

### Phase 4: 동기화 페이지 (2일)

| 태스크 | 설명 | 산출물 |
|--------|------|--------|
| T4.1 | NasSyncPanel 구현 | NAS 상세 패널 |
| T4.2 | SheetsSyncPanel 구현 | Sheets 상세 패널 |
| T4.3 | SyncHistory 구현 | 히스토리 테이블 |
| T4.4 | 수동 동기화 기능 | 트리거 버튼 |

### Phase 5: 테스트 및 배포 (2일)

| 태스크 | 설명 | 산출물 |
|--------|------|--------|
| T5.1 | 컴포넌트 테스트 | Vitest |
| T5.2 | E2E 테스트 | Playwright |
| T5.3 | Docker 통합 | docker-compose 업데이트 |
| T5.4 | 문서화 | README, API 문서 |

---

## 9. 환경 변수

```env
# Frontend (.env)
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
VITE_APP_TITLE=GGP Poker Video Catalog

# Backend 추가 (.env)
CORS_ORIGINS=["http://localhost:5173", "http://localhost:3000"]
WS_HEARTBEAT_INTERVAL=30
```

---

## 10. 구현 상태

### 10.1 현재 파일 수

| 카테고리 | 파일 수 | 한도 | 비율 |
|---------|--------|------|------|
| TypeScript/TSX | 37개 | 40개 | 92.5% |

### 10.2 구현 완료 기능

| 기능 | 상태 | 설명 |
|------|------|------|
| 대시보드 UI | ✅ | DashboardStats, SyncStatusCard, RecentActivityFeed |
| 동기화 관리 | ✅ | Sync 페이지, 히스토리, 수동 트리거 |
| 실시간 연결 | ✅ | WebSocket Hook, 자동 재연결 |
| 로그 검색/필터 | ✅ | SearchInput, Select, 필터링 로직 |
| 에러 처리 | ✅ | ErrorBoundary, 에러 복구 |
| 알림 토스트 | ✅ | ToastContainer, 자동 dismiss |
| 상태 관리 | ✅ | Zustand (syncStore, dashboardStore) |
| API 캐싱 | ✅ | TanStack Query |

### 10.4 Backend API 구현 완료 (v1.3.0)

| 엔드포인트 | 상태 | 파일 |
|-----------|------|------|
| `GET /api/dashboard/stats` | ✅ | `backend/src/api/dashboard.py:75` |
| `GET /api/dashboard/health` | ✅ | `backend/src/api/dashboard.py:145` |
| `GET /api/dashboard/sync/status` | ✅ | `backend/src/api/dashboard.py:206` |
| `WS /ws/sync` | ✅ | `backend/src/api/websocket.py:64` |
| `POST /api/sync/trigger/{source}` | ✅ | `backend/src/api/sync.py:461` |
| `GET /api/sync/jobs/{sync_id}` | ✅ | `backend/src/api/sync.py:649` |
| `GET /api/sync/history` | ✅ | `backend/src/api/sync.py:690` |

**WebSocket 이벤트 브로드캐스트 함수:**

| 함수 | 용도 | 파일 |
|------|------|------|
| `broadcast_sync_start()` | 동기화 시작 알림 | `backend/src/api/websocket.py:122` |
| `broadcast_sync_progress()` | 진행률 업데이트 | `backend/src/api/websocket.py:137` |
| `broadcast_sync_complete()` | 완료 알림 | `backend/src/api/websocket.py:162` |
| `broadcast_sync_error()` | 에러 알림 | `backend/src/api/websocket.py:189` |

### 10.3 추가된 컴포넌트 (v1.2.0)

```
frontend/src/components/common/
├── ErrorBoundary.tsx    # React 에러 바운더리
├── Toast.tsx            # 알림 토스트 컨테이너
├── SearchInput.tsx      # Debounced 검색 입력
└── Select.tsx           # 드롭다운 선택
```

---

## 11. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.3.0 | 2025-12-09 | Backend API 구현: WebSocket, Dashboard, Sync Trigger 엔드포인트 |
| 1.2.0 | 2025-12-09 | ErrorBoundary, Toast, SearchInput, Select 추가, Logs 페이지 필터링 |
| 1.1.0 | 2025-12-09 | 블럭 규칙(.block_rules) 상세 추가, 격리 원칙 명시, PRD v1.1.0 참조 |
| 1.0.0 | 2025-12-09 | 초기 버전 |

---

**문서 버전**: 1.3.0
**작성일**: 2025-12-09
**상태**: Implemented (Frontend + Backend API)
**담당 Block**: BLOCK_FRONTEND
**전담 에이전트**: FrontendAgent
**파일 수**: 37개 / 40개 한도
