# LLD 04: Docker Deployment Design

> **버전**: 1.0.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09

---

## 1. 개요

Docker Compose 기반 배포 설계. PostgreSQL, Redis, Sync Worker 3개 컨테이너로 구성.

### 1.1 컨테이너 구성

```
┌─────────────────────────────────────────────────────┐
│                  docker-compose                      │
├─────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │  postgres  │  │   redis    │  │sync-worker │    │
│  │    :5432   │  │   :6379    │  │  (cron)    │    │
│  └────────────┘  └────────────┘  └────────────┘    │
│         │               │               │           │
│         └───────────────┴───────────────┘           │
│                         │                           │
│  ┌──────────────────────┴──────────────────────┐   │
│  │                  Volumes                     │   │
│  │  - postgres_data                             │   │
│  │  - redis_data                                │   │
│  │  - /mnt/nas:/nas:ro                          │   │
│  │  - ./config:/app/config:ro                   │   │
│  │  - ./logs:/app/logs                          │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 2. docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: pokervod-db
    environment:
      POSTGRES_DB: pokervod
      POSTGRES_USER: ${DB_USER:-pokervod}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pokervod"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: pokervod-redis
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

  sync-worker:
    build:
      context: .
      dockerfile: Dockerfile.sync
    container_name: pokervod-sync
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    environment:
      DATABASE_URL: postgresql://${DB_USER:-pokervod}:${DB_PASSWORD}@postgres:5432/pokervod
      REDIS_URL: redis://redis:6379/0
      NAS_MOUNT_PATH: /nas
      SYNC_INTERVAL_HOURS: ${SYNC_INTERVAL_HOURS:-1}
      GOOGLE_CREDENTIALS_PATH: /app/config/gcp-credentials.json
      SHEET_ID_HAND_ANALYSIS: ${SHEET_ID_HAND_ANALYSIS}
      SHEET_ID_HAND_DATABASE: ${SHEET_ID_HAND_DATABASE}
    volumes:
      - /mnt/nas:/nas:ro
      - ./config:/app/config:ro
      - ./logs:/app/logs
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

---

## 3. Dockerfile.sync

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드
COPY src/ ./src/

# 로그 디렉토리
RUN mkdir -p /app/logs

# 스케줄러 실행
CMD ["python", "-m", "src.sync_scheduler"]
```

---

## 4. 환경 변수

### 4.1 .env 파일

```bash
# Database
DB_USER=pokervod
DB_PASSWORD=<secure-password>

# Sync
SYNC_INTERVAL_HOURS=1

# Google Sheets
SHEET_ID_HAND_ANALYSIS=1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4
SHEET_ID_HAND_DATABASE=1pUMPKe-OsKc-Xd8lH1cP9ctJO4hj3keXY5RwNFp2Mtk

# Optional
LOG_LEVEL=INFO
TZ=Asia/Seoul
```

### 4.2 필수 파일

| 파일 | 경로 | 설명 |
|------|------|------|
| GCP 서비스 계정 | `./config/gcp-credentials.json` | Google Sheets API |
| 동기화 스케줄 | `./config/sync_schedule.yaml` | 스케줄 설정 |
| 초기 SQL | `./init.sql` | DB 초기화 (DDL + Seed) |

---

## 5. NAS 마운트

### 5.1 Linux (Docker Host)

```bash
# SMB 마운트
sudo mount -t cifs \
  //10.10.100.122/docker/GGPNAs/ARCHIVE \
  /mnt/nas \
  -o username=GGP,password=<password>,ro,vers=3.0

# fstab 영구 마운트
# /etc/fstab
//10.10.100.122/docker/GGPNAs/ARCHIVE /mnt/nas cifs \
  credentials=/etc/samba/credentials,ro,vers=3.0 0 0
```

### 5.2 Windows (개발용)

```powershell
# 네트워크 드라이브 연결
net use Z: \\10.10.100.122\docker\GGPNAs\ARCHIVE /user:GGP <password>

# Docker Desktop에서 Z: 드라이브 공유 설정 필요
```

---

## 6. 운영 명령어

### 6.1 기본 명령어

```bash
# 서비스 시작
docker-compose up -d

# 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f sync-worker

# 서비스 중지
docker-compose down

# 서비스 재시작
docker-compose restart sync-worker
```

### 6.2 수동 동기화

```bash
# 전체 동기화
docker exec pokervod-sync python -m src.manual_sync --all

# NAS만
docker exec pokervod-sync python -m src.manual_sync --nas-only

# Sheets만
docker exec pokervod-sync python -m src.manual_sync --sheets-only

# 특정 프로젝트
docker exec pokervod-sync python -m src.manual_sync --project WSOP
```

### 6.3 DB 접속

```bash
# psql 접속
docker exec -it pokervod-db psql -U pokervod -d pokervod

# 백업
docker exec pokervod-db pg_dump -U pokervod pokervod > backup.sql

# 복원
cat backup.sql | docker exec -i pokervod-db psql -U pokervod -d pokervod
```

---

## 7. 헬스체크

### 7.1 컨테이너 상태

```bash
# 전체 상태
docker-compose ps

# 헬스 상태
docker inspect --format='{{.State.Health.Status}}' pokervod-db
```

### 7.2 동기화 상태

```bash
# 동기화 상태 확인
docker exec pokervod-sync python -m src.sync_status

# DB에서 직접 확인
docker exec pokervod-db psql -U pokervod -d pokervod -c \
  "SELECT * FROM v_sync_status;"
```

---

## 8. 로그 관리

### 8.1 로그 위치

```
./logs/
├── sync.log          # 동기화 로그
├── nas_scan.log      # NAS 스캔 로그
├── sheet_sync.log    # Sheets 동기화 로그
└── error.log         # 에러 로그
```

### 8.2 로그 로테이션

```python
# src/logging_config.py
LOGGING = {
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/logs/sync.log',
            'maxBytes': 10_000_000,  # 10MB
            'backupCount': 5,
        }
    }
}
```

---

## 9. 보안

### 9.1 네트워크 격리

```yaml
# docker-compose.yml에 추가
networks:
  pokervod-net:
    driver: bridge

services:
  postgres:
    networks:
      - pokervod-net
  redis:
    networks:
      - pokervod-net
  sync-worker:
    networks:
      - pokervod-net
```

### 9.2 시크릿 관리

```bash
# Docker Secrets (Swarm 모드)
echo "password" | docker secret create db_password -

# 또는 .env 파일 권한 제한
chmod 600 .env
```

---

## 10. 참조

| 문서 | 설명 |
|------|------|
| [LLD_INDEX.md](./LLD_INDEX.md) | LLD 인덱스 |
| [02_SYNC_SYSTEM.md](./02_SYNC_SYSTEM.md) | 동기화 시스템 |
| [PRD.md](../PRD.md) | PRD (Section 8) |

---

**문서 버전**: 1.0.0
**작성일**: 2025-12-09
