# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**버전**: 1.6.1 | **Context**: Windows, PowerShell

---

## 프로젝트 개요

GGP Poker Video Catalog: NAS(19TB, 1,856 파일)와 Google Sheets를 PostgreSQL에 동기화하는 비디오 카탈로그 시스템.

```
db_architecture/
├── backend/              # FastAPI 백엔드 (Python 3.11)
│   ├── src/              # 소스 코드 (main.py, api/, services/, models/)
│   ├── tests/            # pytest 테스트
│   └── docker/           # Docker Compose 설정
├── frontend/             # React 대시보드 (Vite + TypeScript)
│   └── src/              # 컴포넌트, 페이지
├── src/agents/           # Block Agent System (Python)
│   ├── core/             # BaseAgent, Registry, EventBus
│   ├── blocks/           # Parser, Sync, Storage, Query, Export
│   └── orchestrator/     # 워크플로우 실행기
└── docs/lld/             # Low-Level Design 문서
```

---

## 개발 명령어

### Docker (Production)

```powershell
# 전체 스택 시작 (DB + API + Frontend)
cd D:\AI\claude01\db_architecture\backend\docker
docker-compose up -d

# 로그 확인
docker logs pokervod-api -f
docker logs pokervod-db -f

# 컨테이너 상태
docker ps --filter "name=pokervod"
```

### Docker (Development with Hot Reload)

```powershell
cd D:\AI\claude01\db_architecture\backend\docker
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Backend 테스트

```powershell
cd D:\AI\claude01\db_architecture\backend

# 전체 테스트 (SQLite in-memory, DB 연결 불필요)
pytest tests/ -v

# 단일 파일 테스트
pytest tests/api/test_projects.py -v

# 커버리지
pytest tests/ --cov=src --cov-report=term-missing
```

### Frontend 개발

```powershell
cd D:\AI\claude01\db_architecture\frontend

npm run dev      # Vite dev server (localhost:5173)
npm run build    # Production 빌드
npm run lint     # ESLint
```

### Agent System 테스트

```powershell
cd D:\AI\claude01\db_architecture

pytest tests/agents/ -v
pytest tests/agents/test_parser_agent.py -v
```

---

## 서비스 URL

| 서비스 | URL | 비고 |
|--------|-----|------|
| Dashboard | http://localhost:8080 | Nginx (Production) |
| API Docs | http://localhost:9000/docs | Swagger UI |
| WebSocket | ws://localhost:8080/ws/sync | 실시간 동기화 |
| Frontend Dev | http://localhost:5173 | Vite (Development) |

---

## 핵심 규칙

> **전역 규칙 적용**: [상위 CLAUDE.md](../CLAUDE.md) 참조
>
> 추가 규칙: 절대 경로 `D:\AI\claude01\db_architecture\...` 사용

---

## 아키텍처

### 시스템 구조

```
User → :8080 (nginx) → /api/* → :8000 (FastAPI) → :5432 (PostgreSQL)
                     → /ws/*  → WebSocket
                     → /*     → React SPA

NAS (Z:\GGPNAs\ARCHIVE) ─┐
                         ├→ Sync Worker → PostgreSQL (pokervod)
Google Sheets ───────────┘
```

### 데이터 계층 (Hierarchical)

```
Project → Season → Event → Episode → VideoFile
  (7개)    (연도)   (대회)   (영상)    (파일)
                              ↓
                          HandClip ←→ Player, Tag
```

### 주요 프로젝트 코드

| Code | 설명 | 파일명 패턴 예시 |
|------|------|-----------------|
| WSOP | World Series of Poker | `10-wsop-2024-be-ev-21-25k-nlh-hr-ft-title.mp4` |
| HCL | Hustler Casino Live | (준비중) |
| GGMILLIONS | GGPoker Millions | `250507_Super High Roller...mp4` |
| GOG | Game of Gold | `E01_GOG_final_edit_20231215.mp4` |
| PAD | Poker After Dark | `PAD S12 E01.mp4` |
| MPP | MSPT, WPT, HPT 등 | `$1M GTD $1K Mystery Bounty.mp4` |

### Block Agent System 도입 기준

> **중요**: 코드베이스가 **50개+ 파일, 20K+ 라인** 도달 시 재검토
>
> 현재 (~20개 파일, ~5K 라인): **단순 모놀리식 구조**가 효율적

---

## Frontend 개발 주의사항

### API URL 설정 (중요!)

```
┌─────────────────────────────────────────────────────────────┐
│ Production (Docker)  : 상대 경로 사용 → Nginx 프록시 처리   │
│ Development (Vite)   : 환경변수로 직접 URL 지정             │
└─────────────────────────────────────────────────────────────┘
```

| 환경 | API 요청 | WebSocket | 설정 방법 |
|------|---------|-----------|-----------|
| **Production** | `/api/*` | `ws://현재호스트/ws/*` | 기본값 (상대 경로) |
| **Development** | `http://localhost:9000/api/*` | `ws://localhost:9000/ws/*` | `.env.local` 설정 |

### 개발 환경 설정

```bash
# frontend/.env.local (개발 시에만)
VITE_API_BASE_URL=http://localhost:9000
VITE_WS_BASE_URL=ws://localhost:9000
```

### 흔한 실수와 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| `ERR_CONNECTION_REFUSED :8000` | 절대 URL 하드코딩 | 상대 경로 사용 또는 환경변수 |
| WebSocket 연결 실패 | 잘못된 포트/프로토콜 | `window.location` 기반 동적 URL |
| CORS 에러 | 다른 origin 직접 호출 | Nginx 프록시 경유 |

> **원칙**: Production에서는 항상 **상대 경로** (`/api/*`)를 사용하여 Nginx 프록시를 통해 API에 접근

---

## 데이터베이스 작업 지침

### 문서 수정 시 우선순위

| 작업 | 수행 방법 |
|------|----------|
| **문서 수정** | 대상 파일을 직접 Read하여 내용 확인 |
| **스키마 변경** | 기존 DDL 파일 확인 후 Edit 도구로 수정 |
| **검색, 탐색** | 여러 문서 탐색 필요 시 Task 에이전트 활용 |

### 신규 SQL DDL 작성

```
1. 기존 테이블과 관계 확인 후 대상 파일 특정
2. DDL 추가 시 기존 파일에 Edit
3. View/Trigger 등 복잡한 객체는 별도 섹션
```

### 문서화 우선순위

- **사용자가 요청한 내용**: 가장 먼저 문서화
- **암묵적 변경**: 중요 변경은 관련 문서에 반영
- **변경 이력**: 스키마 변경은 반드시 버전 기록

---

## 문서 버전 관리

### 버전 형식

```markdown
> **버전**: X.Y.Z | **기준 PRD**: v5.1 | **작성일**: YYYY-MM-DD | **수정일**: YYYY-MM-DD

### 변경 이력
| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| X.Y.Z | YYYY-MM-DD | 변경 내용 요약 |
```

### 버전 번호 규칙

- **Major (X)**: 대규모 변경, 호환성 깨지는 변경
- **Minor (Y)**: 기능 추가, 섹션 신규/삭제
- **Patch (Z)**: 오타 수정, 설명 보완, 문서 정리

### ⚠️ 문서 수정 시 필수 표기 규칙

> **중요**: 모든 LLD 문서 수정 시 반드시 아래 사항을 준수할 것

1. **문서 상단 버전 업데이트**: `버전: X.Y.Z` 값을 수정 내용에 맞게 증가
2. **문서 하단 상태 필드 업데이트**:
   ```markdown
   **상태**: Updated vX.Y.Z - [수정 내용 요약]
   ```
3. **변경 이력 테이블에 새 항목 추가**: 날짜, 버전, 변경 내용 기록
4. **수정일 갱신**: `수정일: YYYY-MM-DD` 값을 현재 날짜로 변경

**예시**:
```markdown
**문서 버전**: 1.3.0
**수정일**: 2025-12-10
**상태**: Updated v1.3.0 - Issue #28 무한 스크롤 및 DB 매핑 설계 추가

| 1.3.0 | 2025-12-10 | Issue #28: Section 9.6-9.9 추가 (Cursor 페이지네이션) |
```

> 이 규칙을 준수하면 사용자가 검증 시 현재 버전과 최근 변경사항을 즉시 확인할 수 있습니다.

### ⚠️ Frontend 페이지 수정 시 필수 표기 규칙

> **중요**: Frontend 주요 페이지 수정 시 반드시 아래 사항을 준수할 것

1. **파일 상단 JSDoc 버전 업데이트**:
   ```tsx
   /**
    * Page Name - 페이지 설명
    *
    * @version X.Y.Z
    * @updated YYYY-MM-DD
    * @changes [수정 내용 요약]
    */
   ```

2. **PAGE_VERSION 상수 업데이트** (UI 하단에 표시됨):
   ```tsx
   const PAGE_VERSION = {
     version: 'X.Y.Z',
     updated: 'YYYY-MM-DD',
     changes: '[수정 내용 요약]',
   };
   ```

3. **페이지 제목 아래에 버전 표시 UI 포함**:
   ```tsx
   {/* Page Header */}
   <div>
     <h2 className="text-2xl font-bold">페이지 제목</h2>
     <p className="text-gray-500 mt-1">페이지 설명</p>
     <div className="mt-2 text-xs text-gray-400 flex items-center gap-2">
       <span className="bg-gray-100 px-2 py-0.5 rounded">
         📋 v{PAGE_VERSION.version}
       </span>
       <span>{PAGE_VERSION.updated}</span>
       <span className="text-gray-300">|</span>
       <span>{PAGE_VERSION.changes}</span>
     </div>
   </div>
   ```

> 이 규칙을 준수하면 사용자가 브라우저에서 페이지 진입 시 바로 버전을 확인할 수 있습니다.

---

## GitHub 이슈 연동

### 이슈 참조 형식

문서 내 이슈 참조: `#이슈번호` (예: #7 bracelets UNIQUE 제약조건)

### PR 생성 형식

```bash
# 이슈 일괄 해결
gh pr create --title "fix: resolve issues #1-15" --body "Closes #1, #2, ..."
```

---

## 현재 구현 상태

| 컴포넌트 | 상태 | 비고 |
|----------|------|------|
| PostgreSQL 15 | ✅ 완료 | Docker (pokervod-db:5432) |
| NAS Sync | ✅ 완료 | 1,856 파일, 19TB |
| File Parser | ✅ 완료 | 7개 프로젝트 패턴 |
| Backend API | ✅ 완료 | FastAPI 14개 엔드포인트 (port 9000) |
| 파일 필터 | ✅ 완료 | is_hidden, hidden_reason |
| 동기화 검수 | ✅ 완료 | PR #24 - 폴더 트리, Sheets 뷰어 |
| Catalog UI | ✅ 완료 | PR #27 - Netflix 스타일 카탈로그 |
| Google Sheets | ✅ 완료 | Issue #30: Nas Folder Link → video_file_id 연결 구현 |
| Block Agent | ❌ 미구현 | 50+ 파일 도달 시 재검토 |

---

## 🔄 다음 세션 시작점

> **마지막 업데이트**: 2025-12-10

### 현재 브랜치

```
fix/issue-23-sync-inspection
```

### Docker 컨테이너 상태

| 서비스 | 포트 | 상태 |
|--------|------|------|
| pokervod-db | 5432 | ✅ healthy |
| pokervod-api | 9000 | ✅ healthy |
| pokervod-frontend | 8080 | ✅ healthy |

### 최근 완료된 작업

- [x] **Issue #30**: Google Sheets Nas Folder Link → video_file_id 연결 구현
  - NasPathNormalizer: UNC/Docker 경로 → DB 경로 변환
  - VideoFileMatcher: nas_path로 video_files.id 매칭
  - 16개 테스트 작성 및 통과
- [x] Issue #29: NAS Inventory System - Windows 탐색기 100% 일치
- [x] PR #24: 동기화 데이터 검수 기능 (Issue #23)
- [x] PR #27: Catalog UI 구현 (Issue #26)
- [x] Google Sheets 연동 - 2,490 hand clips 동기화
- [x] Issue #25: HCL 파서 - 폴더만 있고 파일 없음 (won't fix)
- [x] PR #19, #21: Block Agent 문서 PR 정리 (닫음)

### 다음 우선순위 작업

1. **검색 기능** - MeiliSearch 또는 PostgreSQL Full-text
2. **비디오 썸네일** - FFmpeg 기반 자동 생성
3. **Hand Clips UI** - 동기화된 클립 조회 인터페이스

---

## 참조

| 문서 | 설명 |
|------|------|
| [LLD_INDEX.md](./docs/lld/LLD_INDEX.md) | LLD 문서 인덱스 |
| [PRD.md](./docs/PRD.md) | 제품 요구사항 문서 |
| [상위 CLAUDE.md](../CLAUDE.md) | 모노레포 전체 지침 |

---

**문서 버전**: 1.10.0
**작성일**: 2025-12-09
**수정일**: 2025-12-10
**상태**: Updated v1.10.0 - Issue #30: Google Sheets Nas Folder Link → video_file_id 연결 구현

### 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.10.0 | 2025-12-10 | **Issue #30**: Google Sheets Nas Folder Link → video_file_id 연결 (NasPathNormalizer, VideoFileMatcher, 16 tests) |
| 1.9.0 | 2025-12-10 | Issue #28: 시트 이름 변경 - Hand Analysis → Metadata Archive, Hand Database → iconik Metadata (보류) |
| 1.8.0 | 2025-12-10 | Frontend 페이지 수정 시 버전 표기 규칙 추가 (PAGE_VERSION 상수, UI 하단 표시) |
| 1.7.0 | 2025-12-10 | 문서 수정 시 필수 표기 규칙 섹션 추가 (버전, 상태, 변경 이력 업데이트 규칙) |
| 1.6.0 | 2025-12-10 | Google Sheets 연동 완료 (2,490 hand clips), 다음 작업 우선순위 갱신 |
| 1.5.0 | 2025-12-10 | Frontend 개발 주의사항 섹션 추가 (API URL, 환경변수, 흔한 실수) |
| 1.4.0 | 2025-12-10 | Catalog UI 완료 반영, PR/Issue 정리 완료, 다음 작업 업데이트 |
| 1.3.0 | 2025-12-10 | 개발 명령어 섹션 추가, 아키텍처 다이어그램 추가, 프로젝트 코드 테이블 추가 |
| 1.2.0 | 2025-12-10 | 다음 세션 시작점 섹션 추가, Issue #23 완료 반영, API 포트 9000 변경 |
| 1.1.0 | 2025-12-09 | Block Agent 도입 기준 추가, 현재 구현 상태 섹션 추가, 카탈로그 UI 방향 추가 |
| 1.0.0 | 2025-12-09 | 초기 버전 |
