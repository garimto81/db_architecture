# LLD 02: Sync System Design

> **버전**: 1.1.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09 | **수정일**: 2025-12-09

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
    """NAS 파일 증분 스캔 서비스"""

    def incremental_scan(self, project_code: str) -> ScanResult:
        # 1. 체크포인트 조회
        checkpoint = self.get_checkpoint(project_code)
        last_mtime = checkpoint.last_file_mtime

        # 2. 신규/수정 파일 검색
        files = self.scan_newer_than(project_code, last_mtime)

        # 3. 빈 파일 목록 처리 (IndexError 방지)
        if not files:
            self.logger.info(f"[{project_code}] No new files found")
            return ScanResult(
                project_code=project_code,
                scanned_count=0,
                new_count=0,
                updated_count=0,
                status='success'
            )

        # 4. 파일별 처리 (배치 단위로 BULK INSERT)
        batch_size = 100
        for batch in self._chunked(files, batch_size):
            records = []
            for file in batch:
                parsed = self.parser_factory.parse(file, project_code)
                media_info = self.ffprobe.analyze(file)
                records.append(self._build_record(parsed, media_info))

            # BULK UPSERT (성능 최적화)
            self.bulk_upsert_video_files(records)

        # 5. 체크포인트 업데이트 (최신 mtime 사용)
        max_mtime = max(f.mtime for f in files)
        self.update_checkpoint(project_code, max_mtime=max_mtime)

        return ScanResult(
            project_code=project_code,
            scanned_count=len(files),
            new_count=self._count_new,
            updated_count=self._count_updated,
            status='success'
        )

    def _chunked(self, iterable, size):
        """리스트를 chunk 단위로 분할"""
        for i in range(0, len(iterable), size):
            yield iterable[i:i + size]
```

### 3.2 BULK INSERT 최적화

```python
def bulk_upsert_video_files(self, records: List[dict]) -> None:
    """
    PostgreSQL COPY 또는 executemany를 활용한 대량 삽입

    성능: 개별 INSERT 대비 10-50x 빠름
    """
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(VideoFile).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=['file_path'],
        set_={
            'file_size_bytes': stmt.excluded.file_size_bytes,
            'file_mtime': stmt.excluded.file_mtime,
            'scan_status': 'scanned',
            'updated_at': func.now()
        }
    )
    self.session.execute(stmt)
    self.session.commit()
```

### 3.3 프로젝트별 스캔 경로

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
    """Google Sheets 동기화 서비스"""

    BATCH_SIZE = 100  # Rate Limit 대응용 배치 크기

    def incremental_sync(self, sheet_id: str) -> SyncResult:
        # 1. 마지막 동기화 행 조회
        sync_state = self.get_sync_state(sheet_id)
        last_row = sync_state.last_row_synced

        # 2. 신규 행 조회 (gspread) - 배치 단위로 요청
        worksheet = self.client.open_by_key(sheet_id).sheet1
        total_rows = worksheet.row_count

        # 배치 단위로 처리 (Rate Limit 대응)
        processed_count = 0
        for batch_start in range(last_row + 1, total_rows + 1, self.BATCH_SIZE):
            batch_end = min(batch_start + self.BATCH_SIZE - 1, total_rows)
            new_rows = worksheet.get(f'A{batch_start}:Z{batch_end}')

            if not new_rows:
                break

            # 3. 배치 내 행별 처리 (BULK INSERT 준비)
            clip_records = []
            tag_links = []
            player_links = []

            for idx, row in enumerate(new_rows):
                if not row or not row[0]:  # 빈 행 스킵
                    continue

                hand_clip = self.parse_row(row, sheet_id)
                hand_clip['sheet_row_number'] = batch_start + idx
                clip_records.append(hand_clip)

                tags = self.normalize_tags(row)
                players = self.extract_players(row)
                tag_links.append((batch_start + idx, tags))
                player_links.append((batch_start + idx, players))

            # 4. BULK UPSERT
            inserted_ids = self.bulk_upsert_hand_clips(clip_records)

            # 5. 태그/플레이어 연결 (BULK)
            self.bulk_link_tags(inserted_ids, tag_links)
            self.bulk_link_players(inserted_ids, player_links)

            processed_count += len(clip_records)

            # Rate Limit 대응: 배치 간 짧은 대기
            await asyncio.sleep(1)

        # 6. 동기화 상태 업데이트
        self.update_sync_state(sheet_id, last_row + processed_count)

        return SyncResult(
            sheet_id=sheet_id,
            processed_count=processed_count,
            status='success'
        )
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

## 4.3 Episode 매핑 플로우

파싱된 video_file을 적절한 Episode에 연결하는 로직:

```python
class EpisodeMatcher:
    """파일명에서 추출된 메타데이터로 Episode를 매칭"""

    def match_episode(self, parsed: ParsedFile) -> Optional[UUID]:
        """
        Episode 매칭 우선순위:
        1. 정확한 episode_number + event 매칭
        2. day_number + event 매칭
        3. 자동 생성 (새 Episode)
        """

        # 1. 정확한 매칭 시도
        if parsed.episode_number:
            episode = self.db.query(Episode).filter(
                Episode.event_id == parsed.event_id,
                Episode.episode_number == parsed.episode_number
            ).first()
            if episode:
                return episode.id

        # 2. day_number로 매칭 (WSOP 등)
        if parsed.day_number:
            episode = self.db.query(Episode).filter(
                Episode.event_id == parsed.event_id,
                Episode.day_number == parsed.day_number
            ).first()
            if episode:
                return episode.id

        # 3. 자동 생성
        return self._create_episode(parsed)

    def _create_episode(self, parsed: ParsedFile) -> UUID:
        """새 Episode 자동 생성"""
        episode = Episode(
            event_id=parsed.event_id,
            episode_number=parsed.episode_number,
            day_number=parsed.day_number,
            title=parsed.title,
            table_type=parsed.table_type,  # ft, day1, day2 등
            episode_type='full'
        )
        self.db.add(episode)
        self.db.commit()
        return episode.id
```

**프로젝트별 매칭 규칙**:

| 프로젝트 | 매칭 기준 | 예시 |
|----------|----------|------|
| **WSOP** | event_number + table_type | ev-21 + ft → Final Table |
| **PAD** | season_number + episode_number | S12 E01 |
| **GOG** | episode_number + date | E01 + 20231215 |
| **GGMillions** | date + featured_player | 250507 + Joey Ingram |
| **MPP** | buy_in + event_name | $1K Mystery Bounty |

---

## 5. 충돌 해결

### 5.1 충돌 정책

| 상황 | 정책 | 처리 | conflict_status |
|------|------|------|-----------------|
| 동일 ID, 다른 값 | Sheet 우선 | DB 덮어쓰기 | `NULL` |
| DB에만 존재 | 유지 | NAS 스캔 데이터 보존 | `NULL` |
| Sheet에만 존재 | 생성 | 신규 레코드 생성 | `NULL` |
| 양쪽 수정 | 수동 확인 | 플래그 설정 | `detected` |
| 검토 완료 | 자동/수동 | 해결 처리 | `resolved` |
| 추가 검토 필요 | 보류 | 관리자 확인 | `manual_review` |

### 5.2 충돌 감지 및 처리

```sql
-- 충돌 감지 쿼리: DB에서 마지막 동기화 이후 수정된 레코드
SELECT hc.id, hc.title, hc.updated_at AS db_updated, hc.conflict_status
FROM hand_clips hc
WHERE hc.sheet_row_number IS NOT NULL
  AND hc.updated_at > (
      SELECT last_synced_at FROM google_sheet_sync
      WHERE entity_type = 'hand_clip'
  );

-- 충돌 플래그 설정
UPDATE hand_clips
SET conflict_status = 'detected',
    updated_at = NOW()
WHERE id IN (/* 충돌 감지된 ID 목록 */);

-- 충돌 레코드 조회 (관리자용)
SELECT
    hc.id,
    hc.title,
    hc.conflict_status,
    hc.sheet_source,
    hc.sheet_row_number,
    hc.updated_at
FROM hand_clips hc
WHERE hc.conflict_status IS NOT NULL
ORDER BY hc.updated_at DESC;
```

### 5.3 충돌 해결 프로세스

```python
class ConflictResolver:
    """동기화 충돌 해결"""

    def resolve_conflict(self, clip_id: UUID, resolution: str) -> None:
        """
        resolution: 'accept_db' | 'accept_sheet' | 'manual_merge'
        """
        clip = self.db.get(HandClip, clip_id)

        if resolution == 'accept_sheet':
            # Sheet 데이터로 덮어쓰기
            self.sync_from_sheet(clip)
            clip.conflict_status = 'resolved'
        elif resolution == 'accept_db':
            # DB 데이터 유지
            clip.conflict_status = 'resolved'
        else:
            # 수동 검토 대기
            clip.conflict_status = 'manual_review'

        self.db.commit()
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

**문서 버전**: 1.1.0
**작성일**: 2025-12-09
**수정일**: 2025-12-09
**상태**: Updated - Logic/Performance issues fixed

### 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.1.0 | 2025-12-09 | #6 빈 파일 목록 체크 추가, #10 Episode 매핑 플로우, #12 배치 처리 로직, #13 BULK INSERT 최적화, conflict_status 활용 |
| 1.0.0 | 2025-12-09 | 초기 버전 |
