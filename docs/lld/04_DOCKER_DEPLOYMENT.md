# LLD 04: Docker Deployment Design

> **버전**: 2.0.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09

---

## 1. 개요

Docker Compose 기반 Full-Stack 배포 설계. PostgreSQL, FastAPI Backend, React Frontend 3개 컨테이너로 구성.

### 1.1 컨테이너 구성

```
┌────────────────────────────────────────────────────────────────────────┐
│                         docker-compose                                   │
├────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                    │
│  │  postgres  │    │    api     │    │  frontend  │                    │
│  │   :5432    │◀───│   :8000    │◀───│    :80     │───▶ User           │
│  │  (DB)      │    │ (FastAPI)  │    │  (Nginx)   │                    │
│  └────────────┘    └────────────┘    └────────────┘                    │
│         │                │                 │                            │
│         └────────────────┴─────────────────┘                            │
│                        pokervod-net                                      │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                         Volumes                                   │  │
│  │  - postgres_data: DB 영구 저장소                                  │  │
│  │  - /z/GGPNAs/ARCHIVE:/nas/ARCHIVE:ro (NAS 마운트)                │  │
│  │  - ./logs:/app/logs (로그)                                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
```

### 1.2 아키텍처 설명

| 컨테이너 | 역할 | 포트 |
|---------|------|------|
| **postgres** | 데이터베이스 (video_files, projects 등) | 5432 (localhost only) |
| **api** | FastAPI REST API + WebSocket | 8000 (localhost only) |
| **frontend** | React SPA + Nginx (API 프록시) | 8080 (외부 노출) |

**데이터 흐름:**
```
User Browser → :8080 (frontend/nginx) → /api/* proxy → :8000 (api) → :5432 (db)
                                      → /ws/* proxy → WebSocket (api)
                                      → /* static files (React SPA)
```

---

## 2. docker-compose.yml (Production)

```yaml
version: '3.8'

# Network for container communication
networks:
  pokervod-net:
    driver: bridge

services:
  # ============== Database ==============
  db:
    image: postgres:15-alpine
    container_name: pokervod-db
    networks:
      - pokervod-net
    environment:
      POSTGRES_DB: pokervod
      POSTGRES_USER: pokervod
      POSTGRES_PASSWORD: pokervod123
      TZ: Asia/Seoul
    ports:
      - "127.0.0.1:5432:5432"  # Local only for security
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/01-init.sql
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pokervod -d pokervod"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G

  # ============== Backend API ==============
  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: pokervod-api
    networks:
      - pokervod-net
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "127.0.0.1:8000:8000"  # Local only, accessed via frontend nginx
    environment:
      DATABASE_URL: postgresql://pokervod:pokervod123@db:5432/pokervod
      DEBUG: "false"
      CORS_ORIGINS: '["http://localhost:3000", "http://localhost:8080", "http://frontend:80"]'
      APP_NAME: "GGP Poker Video Catalog API"
      APP_VERSION: "1.0.0"
    volumes:
      - /z/GGPNAs/ARCHIVE:/nas/ARCHIVE:ro
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M

  # ============== Frontend Dashboard ==============
  frontend:
    build:
      context: ../../frontend
      dockerfile: Dockerfile
    container_name: pokervod-frontend
    networks:
      - pokervod-net
    depends_on:
      - api
    ports:
      - "8080:80"  # Main entry point
    environment:
      VITE_API_BASE_URL: ""  # Proxied through nginx
      VITE_WS_BASE_URL: ""
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 128M

volumes:
  postgres_data:
    driver: local
```

---

## 3. Dockerfiles

### 3.1 Backend API (docker/Dockerfile)

```dockerfile
# FastAPI Backend Dockerfile
FROM python:3.11-slim

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appgroup src/ ./src/

# Create logs directory
RUN mkdir -p /app/logs && chown -R appuser:appgroup /app/logs

# Switch to non-root user
USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run uvicorn (production mode without reload)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.2 Frontend (frontend/Dockerfile)

```dockerfile
# Frontend Dockerfile - Multi-stage build
# Stage 1: Build React application
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first for caching
COPY package*.json ./
RUN npm ci --silent

# Copy source and build
COPY . .
RUN npm run build

# Stage 2: Production image with Nginx
FROM nginx:alpine AS production

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

### 3.3 Frontend Nginx Config (frontend/nginx.conf)

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml;

    # SPA routing - all routes to index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy to backend
    location /api/ {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy
    location /ws/ {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

---

## 4. 개발 환경 설정

### 4.1 Development docker-compose (docker-compose.dev.yml)

```yaml
version: '3.8'

# Development configuration with hot reload
# Usage: docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

services:
  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile.dev
    volumes:
      - ../src:/app/src  # Hot reload
    environment:
      DEBUG: "true"
    command: ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

  frontend:
    build:
      context: ../../frontend
      dockerfile: Dockerfile.dev
    ports:
      - "5173:5173"  # Vite dev server
    volumes:
      - ../../frontend/src:/app/src  # Hot reload
    environment:
      VITE_API_BASE_URL: "http://localhost:8000"
      VITE_WS_BASE_URL: "ws://localhost:8000"
    command: ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

### 4.2 개발 명령어

```bash
# Production 모드 시작
cd backend/docker
docker-compose up -d

# Development 모드 시작 (핫 리로드)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 로그 확인
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f api
docker-compose logs -f frontend

# 서비스 재빌드
docker-compose build --no-cache frontend

# 서비스 중지
docker-compose down

# 볼륨 포함 완전 삭제
docker-compose down -v
```

---

## 5. 디렉토리 구조

```
db_architecture/
├── backend/
│   ├── docker/
│   │   ├── docker-compose.yml       # Production 설정
│   │   ├── docker-compose.dev.yml   # Development 오버라이드
│   │   ├── Dockerfile               # Backend Production
│   │   ├── Dockerfile.dev           # Backend Development
│   │   ├── init.sql                 # DB 초기화 스크립트
│   │   └── logs/                    # 로그 디렉토리
│   ├── src/
│   │   ├── api/
│   │   │   ├── websocket.py         # WebSocket 엔드포인트
│   │   │   ├── dashboard.py         # Dashboard API
│   │   │   └── sync.py              # Sync Trigger API
│   │   ├── main.py
│   │   └── ...
│   └── requirements.txt
│
├── frontend/
│   ├── Dockerfile                   # Frontend Production (multi-stage)
│   ├── Dockerfile.dev               # Frontend Development
│   ├── nginx.conf                   # Nginx 설정 (API 프록시)
│   ├── .env.docker                  # Docker 환경 변수
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   │   └── syncApi.ts           # API 클라이언트
│   │   └── ...
│   └── package.json
│
└── docs/
    └── lld/
        └── 04_DOCKER_DEPLOYMENT.md  # 본 문서
```

---

## 6. 운영 명령어

### 6.1 서비스 시작

```bash
# Production 시작
cd backend/docker
docker-compose up -d

# 상태 확인
docker-compose ps

# 헬스체크 확인
docker inspect --format='{{.State.Health.Status}}' pokervod-db
docker inspect --format='{{.State.Health.Status}}' pokervod-api
docker inspect --format='{{.State.Health.Status}}' pokervod-frontend
```

### 6.2 수동 동기화 트리거

```bash
# cURL로 NAS 동기화 트리거
curl -X POST http://localhost:8080/api/sync/trigger/nas

# Sheets 동기화 트리거
curl -X POST http://localhost:8080/api/sync/trigger/sheets

# 동기화 상태 확인
curl http://localhost:8080/api/sync/status

# 대시보드 통계 확인
curl http://localhost:8080/api/dashboard/stats
```

### 6.3 DB 관리

```bash
# psql 접속
docker exec -it pokervod-db psql -U pokervod -d pokervod

# 백업
docker exec pokervod-db pg_dump -U pokervod pokervod | gzip > backup_$(date +%Y%m%d).sql.gz

# 복원
gunzip -c backup_YYYYMMDD.sql.gz | docker exec -i pokervod-db psql -U pokervod -d pokervod
```

---

## 7. 접속 URL

| 서비스 | URL | 설명 |
|--------|-----|------|
| **Dashboard** | http://localhost:8080 | Frontend React SPA |
| **API Docs** | http://localhost:8080/api/docs | Swagger UI (via nginx proxy) |
| **API Direct** | http://localhost:8000/docs | Swagger UI (직접 접속) |
| **WebSocket** | ws://localhost:8080/ws/sync | 실시간 동기화 이벤트 |

---

## 8. 보안 체크리스트

| 항목 | 상태 | 설명 |
|------|------|------|
| 네트워크 격리 | ✅ | `pokervod-net` 브릿지 네트워크 |
| PostgreSQL 로컬 전용 | ✅ | `127.0.0.1:5432` |
| API 로컬 전용 | ✅ | `127.0.0.1:8000` (nginx 프록시 통해 접근) |
| Non-root 컨테이너 | ✅ | Backend `USER appuser` |
| 리소스 제한 | ✅ | `deploy.resources.limits` |
| 헬스체크 | ✅ | 모든 컨테이너 |
| Nginx 보안 헤더 | ✅ | X-Frame-Options, X-Content-Type-Options |
| Read-only NAS | ✅ | `:ro` 마운트 |

---

## 9. 트러블슈팅

### 9.1 Frontend 빌드 실패

```bash
# 캐시 삭제 후 재빌드
docker-compose build --no-cache frontend

# 로그 확인
docker-compose logs frontend
```

### 9.2 WebSocket 연결 실패

```bash
# nginx 프록시 설정 확인
docker exec pokervod-frontend cat /etc/nginx/conf.d/default.conf

# API 서버 직접 테스트
wscat -c ws://localhost:8000/ws/sync
```

### 9.3 DB 연결 실패

```bash
# DB 헬스 확인
docker exec pokervod-db pg_isready -U pokervod -d pokervod

# 연결 테스트
docker exec pokervod-api python -c "from src.database import engine; print(engine.connect())"
```

---

## 10. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 2.0.0 | 2025-12-09 | Full-Stack 배포: Frontend + Backend + DB 통합 |
| 1.1.0 | 2025-12-09 | 보안 강화 (Docker Secrets, Non-root, Network isolation) |
| 1.0.0 | 2025-12-08 | 초기 버전 (DB + Sync Worker) |

---

**문서 버전**: 2.0.0
**작성일**: 2025-12-09
**상태**: Implemented
