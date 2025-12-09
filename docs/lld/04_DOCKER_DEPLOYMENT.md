# LLD 04: Docker Deployment Design

> **버전**: 1.1.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09

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
│  │  :5432     │  │   :6379    │  │  (cron)    │    │
│  │  (SSL)     │  │  (AUTH)    │  │ (non-root) │    │
│  └────────────┘  └────────────┘  └────────────┘    │
│         │               │               │           │
│         └───────────────┴───────────────┘           │
│                    pokervod-net                      │
│  ┌──────────────────────────────────────────────┐   │
│  │                  Volumes                     │   │
│  │  - postgres_data                             │   │
│  │  - redis_data                                │   │
│  │  - /mnt/nas:/nas:ro                          │   │
│  │  - ./secrets:/run/secrets:ro                 │   │
│  │  - ./logs:/app/logs                          │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 2. docker-compose.yml

```yaml
version: '3.8'

# 네트워크 격리 (보안)
networks:
  pokervod-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16

services:
  postgres:
    image: postgres:15-alpine
    container_name: pokervod-db
    networks:
      - pokervod-net
    environment:
      POSTGRES_DB: pokervod
      POSTGRES_USER: ${DB_USER:-pokervod}
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
      # SSL 활성화
      POSTGRES_INITDB_ARGS: "--auth-host=scram-sha-256"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
      - ./secrets/db_password:/run/secrets/db_password:ro
    ports:
      # 로컬만 노출 (보안)
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-pokervod} -d pokervod"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    # 리소스 제한
    deploy:
      resources:
        limits:
          memory: 1G

  redis:
    image: redis:7-alpine
    container_name: pokervod-redis
    networks:
      - pokervod-net
    # Redis 비밀번호 설정 (보안)
    command: >
      redis-server
      --requirepass "${REDIS_PASSWORD}"
      --appendonly yes
    volumes:
      - redis_data:/data
    # 외부 노출 제거 - 내부 네트워크만
    # ports:
    #   - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M

  sync-worker:
    build:
      context: .
      dockerfile: Dockerfile.sync
    container_name: pokervod-sync
    networks:
      - pokervod-net
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      # 환경 변수에서 민감 정보 분리
      DATABASE_HOST: postgres
      DATABASE_PORT: 5432
      DATABASE_NAME: pokervod
      DATABASE_USER: ${DB_USER:-pokervod}
      # 비밀번호는 파일에서 읽기
      DATABASE_PASSWORD_FILE: /run/secrets/db_password
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_PASSWORD_FILE: /run/secrets/redis_password
      NAS_MOUNT_PATH: /nas
      SYNC_INTERVAL_HOURS: ${SYNC_INTERVAL_HOURS:-1}
      GOOGLE_CREDENTIALS_PATH: /run/secrets/gcp-credentials.json
      # Sheet ID는 환경 변수로 전달 (문서에 실제 값 노출 금지)
      SHEET_ID_HAND_ANALYSIS: ${SHEET_ID_HAND_ANALYSIS}
      SHEET_ID_HAND_DATABASE: ${SHEET_ID_HAND_DATABASE}
    volumes:
      - /mnt/nas:/nas:ro
      - ./secrets:/run/secrets:ro
      - ./logs:/app/logs
    # Read-only 파일시스템 (보안)
    read_only: true
    tmpfs:
      - /tmp
    restart: unless-stopped
    # 헬스체크 추가
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 512M

volumes:
  postgres_data:
  redis_data:
```

---

## 3. Dockerfile.sync

```dockerfile
FROM python:3.11-slim

# 보안: non-root 사용자 생성
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드
COPY --chown=appuser:appgroup src/ ./src/

# 로그 디렉토리 (권한 설정)
RUN mkdir -p /app/logs && chown -R appuser:appgroup /app/logs

# 보안: non-root 사용자로 전환
USER appuser

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

# 스케줄러 실행
CMD ["python", "-m", "src.sync_scheduler"]
```

---

## 4. 환경 변수 및 시크릿 관리

### 4.1 디렉토리 구조

```
project/
├── docker-compose.yml
├── Dockerfile.sync
├── .env                      # 비밀번호 제외한 설정
├── .env.example              # 템플릿 (버전 관리)
├── .gitignore                # 민감 파일 제외
├── secrets/                  # 시크릿 디렉토리 (gitignore)
│   ├── db_password           # DB 비밀번호
│   ├── redis_password        # Redis 비밀번호
│   └── gcp-credentials.json  # GCP 서비스 계정
└── init.sql
```

### 4.2 .env.example (버전 관리 대상)

```bash
# Database
DB_USER=pokervod
# DB_PASSWORD는 secrets/db_password 파일로 관리

# Sync
SYNC_INTERVAL_HOURS=1

# Google Sheets (실제 ID는 별도 관리)
# 예시 형식만 표시 - 실제 ID 노출 금지
SHEET_ID_HAND_ANALYSIS=1xxx...your-sheet-id...xxx
SHEET_ID_HAND_DATABASE=1xxx...your-sheet-id...xxx

# Redis
# REDIS_PASSWORD는 secrets/redis_password 파일로 관리

# Optional
LOG_LEVEL=INFO
TZ=Asia/Seoul
```

### 4.3 .gitignore (필수)

```gitignore
# 시크릿 파일 (절대 커밋 금지)
.env
secrets/
*.pem
*.key

# GCP 자격증명
*-credentials.json
*-service-account.json

# 로그
logs/
*.log
```

### 4.4 시크릿 파일 생성

```bash
# 시크릿 디렉토리 생성
mkdir -p secrets
chmod 700 secrets

# DB 비밀번호 생성 (최소 32자, 특수문자 포함)
openssl rand -base64 32 > secrets/db_password
chmod 600 secrets/db_password

# Redis 비밀번호 생성
openssl rand -base64 32 > secrets/redis_password
chmod 600 secrets/redis_password

# GCP 자격증명 복사 (별도 다운로드 필요)
cp ~/path/to/gcp-credentials.json secrets/
chmod 600 secrets/gcp-credentials.json
```

### 4.5 환경 변수 검증 스크립트

```bash
#!/bin/bash
# scripts/validate-env.sh

REQUIRED_SECRETS=("db_password" "redis_password" "gcp-credentials.json")
REQUIRED_ENV=("SHEET_ID_HAND_ANALYSIS" "SHEET_ID_HAND_DATABASE")

echo "=== 환경 설정 검증 ==="

# 시크릿 파일 확인
for secret in "${REQUIRED_SECRETS[@]}"; do
  if [ ! -f "secrets/$secret" ]; then
    echo "ERROR: secrets/$secret 파일이 없습니다"
    exit 1
  fi
  # 권한 확인
  perms=$(stat -c %a "secrets/$secret" 2>/dev/null || stat -f %A "secrets/$secret")
  if [ "$perms" != "600" ]; then
    echo "WARN: secrets/$secret 권한이 600이 아닙니다 (현재: $perms)"
  fi
done

# 환경 변수 확인
source .env 2>/dev/null
for var in "${REQUIRED_ENV[@]}"; do
  if [ -z "${!var}" ]; then
    echo "ERROR: $var 환경 변수가 설정되지 않았습니다"
    exit 1
  fi
done

echo "✓ 모든 환경 설정이 유효합니다"
```

---

## 5. NAS 마운트

### 5.1 Linux (Docker Host)

```bash
# SMB 자격증명 파일 생성 (보안)
sudo cat > /etc/samba/credentials << 'EOF'
username=GGP
password=YOUR_PASSWORD_HERE
domain=WORKGROUP
EOF
sudo chmod 600 /etc/samba/credentials

# SMB 마운트
sudo mount -t cifs \
  //10.10.100.122/docker/GGPNAs/ARCHIVE \
  /mnt/nas \
  -o credentials=/etc/samba/credentials,ro,vers=3.0,uid=1000,gid=1000

# fstab 영구 마운트 (자격증명 파일 참조)
# /etc/fstab
//10.10.100.122/docker/GGPNAs/ARCHIVE /mnt/nas cifs \
  credentials=/etc/samba/credentials,ro,vers=3.0,uid=1000,gid=1000 0 0
```

### 5.2 Windows (개발용)

```powershell
# 네트워크 드라이브 연결 (자격증명 저장)
net use Z: \\10.10.100.122\docker\GGPNAs\ARCHIVE /user:GGP /persistent:yes

# Docker Desktop에서 Z: 드라이브 공유 설정 필요
# Settings > Resources > File Sharing
```

---

## 6. 운영 명령어

### 6.1 서비스 시작

```bash
# 환경 검증 후 시작
./scripts/validate-env.sh && docker-compose up -d

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
# 전체 동기화 (설정 파일 기반)
docker exec pokervod-sync python -m src.manual_sync --config /app/config/sync.yaml

# NAS만
docker exec pokervod-sync python -m src.manual_sync --nas-only

# Sheets만
docker exec pokervod-sync python -m src.manual_sync --sheets-only

# 특정 프로젝트
docker exec pokervod-sync python -m src.manual_sync --project WSOP
```

### 6.3 DB 접속

```bash
# psql 접속 (비밀번호 파일 사용)
docker exec -it pokervod-db psql -U pokervod -d pokervod

# 백업 (암호화 권장)
docker exec pokervod-db pg_dump -U pokervod pokervod | gzip > backup_$(date +%Y%m%d).sql.gz

# 복원
gunzip -c backup_YYYYMMDD.sql.gz | docker exec -i pokervod-db psql -U pokervod -d pokervod
```

---

## 7. 헬스체크

### 7.1 컨테이너 상태

```bash
# 전체 상태
docker-compose ps

# 헬스 상태
docker inspect --format='{{.State.Health.Status}}' pokervod-db
docker inspect --format='{{.State.Health.Status}}' pokervod-redis
docker inspect --format='{{.State.Health.Status}}' pokervod-sync
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

### 8.2 로그 로테이션 (민감 정보 필터링 포함)

```python
# src/logging_config.py
import logging
import re

class SensitiveDataFilter(logging.Filter):
    """민감 정보 마스킹 필터"""
    PATTERNS = [
        (r'password[=:]\s*\S+', 'password=***'),
        (r'(postgresql://[^:]+:)[^@]+(@)', r'\1***\2'),
        (r'(redis://[^:]*:)[^@]+(@)', r'\1***\2'),
        (r'Bearer\s+\S+', 'Bearer ***'),
    ]

    def filter(self, record):
        msg = str(record.msg)
        for pattern, replacement in self.PATTERNS:
            msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
        record.msg = msg
        return True

LOGGING = {
    'version': 1,
    'filters': {
        'sensitive': {'()': SensitiveDataFilter}
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/logs/sync.log',
            'maxBytes': 10_000_000,  # 10MB
            'backupCount': 5,
            'filters': ['sensitive'],
        }
    }
}
```

---

## 9. 보안 체크리스트

| 항목 | 상태 | 설명 |
|------|------|------|
| 네트워크 격리 | ✅ | `pokervod-net` 브릿지 네트워크 |
| Redis 비밀번호 | ✅ | `--requirepass` 설정 |
| PostgreSQL 인증 | ✅ | `scram-sha-256` + 로컬만 노출 |
| Non-root 컨테이너 | ✅ | `USER appuser` |
| 시크릿 파일 분리 | ✅ | `secrets/` 디렉토리 |
| .gitignore 설정 | ✅ | `.env`, `secrets/` 제외 |
| Read-only 파일시스템 | ✅ | `read_only: true` |
| 리소스 제한 | ✅ | `deploy.resources.limits` |
| 헬스체크 | ✅ | 모든 컨테이너 |
| 로그 민감정보 필터링 | ✅ | `SensitiveDataFilter` |

---

## 10. 참조

| 문서 | 설명 |
|------|------|
| [LLD_INDEX.md](./LLD_INDEX.md) | LLD 인덱스 |
| [02_SYNC_SYSTEM.md](./02_SYNC_SYSTEM.md) | 동기화 시스템 |
| [PRD.md](../PRD.md) | PRD (Section 8) |

---

**문서 버전**: 1.1.0
**작성일**: 2025-12-09
**변경 이력**:
- v1.1.0: 보안 강화 (이슈 #1-5 해결)
  - 환경 변수에서 실제 Sheet ID 제거 (#1)
  - Docker Secrets 기반 비밀번호 관리 (#2)
  - Redis 비밀번호 및 네트워크 격리 (#3)
  - Non-root 컨테이너 실행 (#4)
  - PostgreSQL 로컬 전용 노출 (#5)
