# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**버전**: 1.4.0 | **Context**: Windows, PowerShell

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
| Google Sheets | ⚠️ 미완 | 라이브러리만 설치 |
| Block Agent | ❌ 미구현 | 50+ 파일 도달 시 재검토 |

---

## 🔄 다음 세션 시작점

> **마지막 업데이트**: 2025-12-10

### 현재 브랜치

```
main (최신)
```

### Docker 컨테이너 상태

| 서비스 | 포트 | 상태 |
|--------|------|------|
| pokervod-db | 5432 | ✅ healthy |
| pokervod-api | 9000 | ✅ healthy |
| pokervod-frontend | 8080 | ✅ healthy |

### 최근 완료된 작업

- [x] PR #24: 동기화 데이터 검수 기능 (Issue #23)
- [x] PR #27: Catalog UI 구현 (Issue #26)
- [x] Issue #25: HCL 파서 - 폴더만 있고 파일 없음 (won't fix)
- [x] PR #19, #21: Block Agent 문서 PR 정리 (닫음)

### 다음 우선순위 작업

1. **Google Sheets 동기화 완성** - 실제 연동 구현
2. **검색 기능** - MeiliSearch 또는 PostgreSQL Full-text
3. **비디오 썸네일** - FFmpeg 기반 자동 생성

---

## 참조

| 문서 | 설명 |
|------|------|
| [LLD_INDEX.md](./docs/lld/LLD_INDEX.md) | LLD 문서 인덱스 |
| [PRD.md](./docs/PRD.md) | 제품 요구사항 문서 |
| [상위 CLAUDE.md](../CLAUDE.md) | 모노레포 전체 지침 |

---

**문서 버전**: 1.4.0
**작성일**: 2025-12-09
**수정일**: 2025-12-10

### 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.4.0 | 2025-12-10 | Catalog UI 완료 반영, PR/Issue 정리 완료, 다음 작업 업데이트 |
| 1.3.0 | 2025-12-10 | 개발 명령어 섹션 추가, 아키텍처 다이어그램 추가, 프로젝트 코드 테이블 추가 |
| 1.2.0 | 2025-12-10 | 다음 세션 시작점 섹션 추가, Issue #23 완료 반영, API 포트 9000 변경 |
| 1.1.0 | 2025-12-09 | Block Agent 도입 기준 추가, 현재 구현 상태 섹션 추가, 카탈로그 UI 방향 추가 |
| 1.0.0 | 2025-12-09 | 초기 버전 |
