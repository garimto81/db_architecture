# LLD 02: Sync System Design

> **버전**: 1.0.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09

---

## 1. 개요

NAS와 Google Sheets 데이터를 1시간 주기로 자동 동기화하는 시스템 설계.

### 1.1 동기화 대상

| 소스 | 대상 테이블 | 전략 |
|------|------------|------|
| NAS (SMB) | video_files | mtime 기반 증분 |
| Google Sheet 1 | hand_clips (hand_analysis) | row number 기반 |
| Google Sheet 2 | hand_clips (hand_database) | row number 기반 |

---

## 2. 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    SYNC SCHEDULER                        │
│                   (APScheduler)                          │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌───────────┐   ┌───────────┐   ┌───────────┐
   │NAS Scanner│   │Sheet Sync │   │Validator  │
   │  (1시간)  │   │  (1시간)  │   │  (1일)    │
   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
         │               │               │
         └───────────────┴───────────────┘
                         │
                         ▼
               ┌─────────────────┐
               │   PostgreSQL    │
               │  (pokervod DB)  │
               └─────────────────┘
```

---

## 3. NAS 증분 스캔

### 3.1 스캔 알고리즘

```python
class NasScannerService:
    def incremental_scan(self, project_code: str) -> ScanResult:
        # 1. 체크포인트 조회
        checkpoint = self.get_checkpoint(project_code)
        last_mtime = checkpoint.last_file_mtime

        # 2. 신규/수정 파일 검색
        files = self.scan_newer_than(project_code, last_mtime)

        # 3. 파일별 처리
        for file in files:
            parsed = self.parser_factory.parse(file, project_code)
            media_info = self.ffprobe.analyze(file)
            self.upsert_video_file(parsed, media_info)

        # 4. 체크포인트 업데이트
        self.update_checkpoint(project_code, max_mtime=files[-1].mtime)
```

### 3.2 프로젝트별 스캔 경로

| 프로젝트 | NAS 경로 |
|----------|----------|
| WSOP | `\\10.10.100.122\docker\GGPNAs\ARCHIVE\WSOP` |
| GGMILLIONS | `\\10.10.100.122\docker\GGPNAs\ARCHIVE\GGMillions` |
| MPP | `\\10.10.100.122\docker\GGPNAs\ARCHIVE\MPP` |
| PAD | `\\10.10.100.122\docker\GGPNAs\ARCHIVE\PAD` |
| GOG | `\\10.10.100.122\docker\GGPNAs\ARCHIVE\GOG 최종` |

---

## 4. Google Sheets 동기화

### 4.1 동기화 알고리즘

```python
class SheetSyncService:
    def incremental_sync(self, sheet_id: str) -> SyncResult:
        # 1. 마지막 동기화 행 조회
        sync_state = self.get_sync_state(sheet_id)
        last_row = sync_state.last_row_synced

        # 2. 신규 행 조회 (gspread)
        worksheet = self.client.open_by_key(sheet_id).sheet1
        new_rows = worksheet.get(f'A{last_row + 1}:Z')

        # 3. 행별 처리
        for idx, row in enumerate(new_rows):
            hand_clip = self.parse_row(row, sheet_id)
            tags = self.normalize_tags(row)
            players = self.extract_players(row)

            clip_id = self.upsert_hand_clip(hand_clip)
            self.link_tags(clip_id, tags)
            self.link_players(clip_id, players)

        # 4. 동기화 상태 업데이트
        self.update_sync_state(sheet_id, last_row + len(new_rows))
```

### 4.2 태그 정규화

| 원본 값 | 정규화 | 카테고리 |
|---------|--------|----------|
| "Preflop All-in" | preflop_allin | poker_play |
| "preflop allin" | preflop_allin | poker_play |
| "Bad Beat" | bad_beat | poker_play |
| "BADBEAT" | bad_beat | poker_play |
| "★★★" | ★★★ | hand_grade (직접 저장) |

---

## 5. 충돌 해결

### 5.1 충돌 정책

| 상황 | 정책 | 처리 |
|------|------|------|
| 동일 ID, 다른 값 | Sheet 우선 | DB 덮어쓰기 |
| DB에만 존재 | 유지 | NAS 스캔 데이터 보존 |
| Sheet에만 존재 | 생성 | 신규 레코드 생성 |
| 양쪽 수정 | 수동 확인 | `conflict` 플래그 설정 |

### 5.2 충돌 감지

```sql
-- 충돌 감지 쿼리
SELECT hc.id, hc.title, hc.updated_at AS db_updated
FROM hand_clips hc
WHERE hc.sheet_row_number IS NOT NULL
  AND hc.updated_at > (
      SELECT last_synced_at FROM google_sheet_sync
      WHERE entity_type = 'hand_clip'
  );
```

---

## 6. 스케줄 설정

### 6.1 Cron 스케줄

```yaml
# config/sync_schedule.yaml
schedules:
  nas_scan:
    default: "0 * * * *"    # 매시 정각
    urgent: "*/15 * * * *"  # 15분마다 (대회 기간)

  sheet_sync:
    default: "0 * * * *"    # 매시 정각

  validation:
    daily: "0 3 * * *"      # 매일 03:00
    weekly: "0 4 * * 0"     # 일요일 04:00
```

### 6.2 APScheduler 설정

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler()

# NAS 스캔 (매시)
scheduler.add_job(
    nas_scanner.scan_all,
    CronTrigger.from_crontab('0 * * * *'),
    id='nas_scan'
)

# Sheet 동기화 (매시)
scheduler.add_job(
    sheet_sync.sync_all,
    CronTrigger.from_crontab('0 * * * *'),
    id='sheet_sync'
)

# 일일 검증 (03:00)
scheduler.add_job(
    validator.validate_all,
    CronTrigger.from_crontab('0 3 * * *'),
    id='daily_validation'
)
```

---

## 7. Rate Limit 대응

### 7.1 Google Sheets API 제한

```
제한: 60 requests/minute/user
대응:
1. Exponential Backoff: 1s → 2s → 4s → 8s → max 60s
2. 배치 요청: 100행 단위
3. 요청 큐잉: Redis 기반
```

### 7.2 구현

```python
class RateLimiter:
    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.redis = Redis()

    async def acquire(self):
        key = f"rate_limit:sheets:{datetime.now().minute}"
        count = self.redis.incr(key)
        self.redis.expire(key, self.window)

        if count > self.max_requests:
            wait_time = min(2 ** (count - self.max_requests), 60)
            await asyncio.sleep(wait_time)
```

---

## 8. 모니터링

### 8.1 로그 레벨

| 이벤트 | 레벨 | 액션 |
|--------|------|------|
| 동기화 시작/완료 | INFO | 로그 |
| 신규 파일 감지 | INFO | 로그 |
| Rate Limit | WARN | Backoff |
| 파싱 실패 | WARN | 재시도 |
| 동기화 실패 | ERROR | Slack 알림 |
| 24시간 미동기화 | CRITICAL | Email 알림 |

### 8.2 메트릭

```sql
-- 동기화 성공률
SELECT
    sync_type,
    COUNT(*) FILTER (WHERE status = 'success') * 100.0 / COUNT(*) AS success_rate
FROM sync_logs
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY sync_type;

-- 평균 동기화 시간
SELECT
    sync_type,
    AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) AS avg_duration_sec
FROM sync_logs
WHERE status = 'success'
GROUP BY sync_type;
```

---

## 9. 참조

| 문서 | 설명 |
|------|------|
| [01_DATABASE_SCHEMA.md](./01_DATABASE_SCHEMA.md) | DB 스키마 |
| [03_FILE_PARSER.md](./03_FILE_PARSER.md) | 파일명 파서 |
| [04_DOCKER_DEPLOYMENT.md](./04_DOCKER_DEPLOYMENT.md) | Docker 배포 |

---

**문서 버전**: 1.0.0
**작성일**: 2025-12-09
