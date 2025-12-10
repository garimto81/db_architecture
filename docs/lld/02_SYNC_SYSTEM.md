# LLD 02: Sync System Design

> **버전**: 1.4.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09 | **수정일**: 2025-12-10

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

## 9. Hand Clips 검증 대시보드

### 9.1 개요

사용자가 Google Sheets 동기화 결과를 직접 검증할 수 있는 대시보드 UI.

**배경**: 증분 동기화 방식으로 인해 "0개 추가, 0개 업데이트" 결과가 정상 상황에서도 표시될 수 있어, 실제 동기화된 데이터를 확인할 수 있는 UI 필요.

### 9.2 Backend API

#### 9.2.1 Hand Clips Summary API

```
GET /api/sync/hand-clips/summary
```

**응답 구조**:
```json
{
  "total_clips": 2490,
  "by_source": {
    "hand_analysis": 39,
    "hand_database": 2451
  },
  "latest_sync": "2025-12-10T10:44:12+09:00",
  "sample_clips": [
    {
      "id": "uuid",
      "sheet_source": "hand_database",
      "sheet_row_number": 2403,
      "title": "2009 WSOP ME25 Final Table...",
      "timecode": "1549449",
      "notes": "2009 World Series of Poker",
      "hand_grade": "★★★",
      "created_at": "2025-12-10T10:40:06+09:00"
    }
  ]
}
```

#### 9.2.2 Hand Clips List API

```
GET /api/sync/hand-clips?source=hand_analysis&page=1&page_size=20
```

**파라미터**:
| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| source | string | null | 시트 소스 필터 (hand_analysis, hand_database) |
| page | int | 1 | 페이지 번호 |
| page_size | int | 20 | 페이지 크기 (1-100) |

**응답 구조**:
```json
{
  "items": [/* HandClipResponse[] */],
  "total": 2490,
  "page": 1,
  "page_size": 20,
  "total_pages": 125
}
```

### 9.3 Frontend 컴포넌트

#### 9.3.1 컴포넌트 구조

```
Sync.tsx (페이지)
├── Tab: 동기화 상태 (기존)
├── Tab: 파일 브라우저 (기존)
├── Tab: Sheets 데이터
│   └── SheetsViewer.tsx
│       ├── SheetTabs (시트 선택)
│       ├── SyncSummaryCard (NEW) ← 요약 통계
│       ├── HandClipsTable (NEW) ← 상세 목록
│       └── SchedulerCard (기존)
```

#### 9.3.2 SyncSummaryCard

**표시 정보**:
- 전체 클립 수 (총 2,490개)
- 소스별 클립 수 (hand_analysis: 39, hand_database: 2,451)
- 마지막 동기화 시간
- 증분 동기화 상태 (last_row_synced)

**디자인**:
```
┌─────────────────────────────────────────────────┐
│ 📊 Hand Clips 동기화 현황                        │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐  ┌──────────────┐             │
│  │    2,490     │  │   10:44 AM   │             │
│  │   전체 클립   │  │  마지막 동기화 │             │
│  └──────────────┘  └──────────────┘             │
│                                                 │
│  Hand Analysis:  39 clips (row 71까지)          │
│  Hand Database: 2,451 clips (row 2,453까지)     │
│                                                 │
└─────────────────────────────────────────────────┘
```

#### 9.3.3 HandClipsTable

**테이블 컬럼**:
| 컬럼 | 너비 | 설명 |
|------|------|------|
| 소스 | 100px | hand_analysis / hand_database (뱃지) |
| 제목 | auto | 핸드 클립 제목 (말줄임) |
| 타임코드 | 100px | HH:MM:SS 형식 |
| 등급 | 80px | ★ ~ ★★★ (별 아이콘) |
| 동기화일 | 120px | relative time (예: 2시간 전) |

**필터/검색**:
- 소스 필터 (드롭다운)
- 제목 검색 (debounced input)
- 페이지네이션 (20개씩)

### 9.4 증분 동기화 설명 UI

사용자에게 "0개 추가" 결과가 정상임을 설명하는 인포 박스:

```
┌─────────────────────────────────────────────────┐
│ ℹ️ 증분 동기화 안내                              │
├─────────────────────────────────────────────────┤
│ Google Sheets 동기화는 증분 방식으로 동작합니다.  │
│                                                 │
│ • 이미 동기화된 행은 다시 처리하지 않습니다        │
│ • "0개 추가"는 새 행이 없다는 의미입니다           │
│ • 실제 데이터는 아래 테이블에서 확인하세요         │
│                                                 │
│ 현재 상태: row 2,453까지 동기화 완료              │
└─────────────────────────────────────────────────┘
```

### 9.5 검증 URL

| URL | 설명 |
|-----|------|
| http://localhost:9000/api/sync/hand-clips/summary | 요약 API (브라우저에서 직접 확인) |
| http://localhost:9000/api/sync/hand-clips | 목록 API (페이지네이션) |
| http://localhost:9000/api/sync/video-files | Video Files API (cursor 페이지네이션) |
| http://localhost:9000/api/sync/hand-clips/cursor | Hand Clips API (cursor 페이지네이션) |
| http://localhost:8080/sync → Sheets 탭 | 대시보드 UI |

### 9.6 Cursor 기반 페이지네이션 API (Issue #28)

#### 9.6.1 Offset vs Cursor 비교

| 특성 | Offset (기존) | Cursor (신규) |
|------|--------------|---------------|
| 성능 | O(n) - 대규모 데이터에서 느림 | O(1) - 일정한 성능 |
| 데이터 일관성 | 동시 삽입 시 중복/누락 가능 | 안정적 |
| 무한 스크롤 | 비효율적 | 최적화됨 |
| 구현 복잡도 | 낮음 | 중간 |

#### 9.6.2 Video Files Cursor API

```
GET /api/sync/video-files?cursor={last_id}&limit=50&project_code={code}
```

**파라미터**:

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| cursor | UUID | No | null | 마지막 조회 항목의 ID |
| limit | int | No | 20 | 조회 개수 (1-100) |
| project_code | string | No | null | 프로젝트 코드 필터 |
| scan_status | string | No | null | 스캔 상태 필터 |
| is_hidden | bool | No | null | 숨김 여부 필터 |

**응답 구조**:

```json
{
  "items": [
    {
      "id": "uuid",
      "file_name": "2024_WSOP_ME_D7_FT.mp4",
      "file_path": "\\\\10.10.100.122\\...\\file.mp4",
      "file_size_bytes": 12345678900,
      "display_title": "2024 WSOP Main Event Day 7",
      "resolution": "1920x1080",
      "version_type": "stream",
      "scan_status": "scanned",
      "is_hidden": false,
      "hidden_reason": null,
      "created_at": "2024-12-09T15:30:00+09:00"
    }
  ],
  "next_cursor": "uuid-of-last-item",
  "has_more": true,
  "total": 1856
}
```

#### 9.6.3 Hand Clips Cursor API

```
GET /api/sync/hand-clips/cursor?cursor={last_id}&limit=50&source={sheet_key}
```

**파라미터**:

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| cursor | UUID | No | null | 마지막 조회 항목의 ID |
| limit | int | No | 20 | 조회 개수 (1-100) |
| source | string | No | null | 시트 소스 필터 (hand_analysis, hand_database) |

**응답 구조**:

```json
{
  "items": [
    {
      "id": "uuid",
      "sheet_source": "hand_database",
      "sheet_row_number": 2403,
      "title": "2009 WSOP ME25 Final Table...",
      "timecode": "1549449",
      "notes": "2009 World Series of Poker",
      "hand_grade": "★★★",
      "created_at": "2025-12-10T10:40:06+09:00"
    }
  ],
  "next_cursor": "uuid-of-last-item",
  "has_more": true,
  "total": 2490
}
```

### 9.7 DB 매핑 정보 표시

#### 9.7.1 개요

Google Sheets 데이터가 DB 테이블에 어떻게 매핑되는지 시각적으로 표시합니다.
사용자가 동기화 결과를 검증할 때 원본 데이터와 DB 저장 구조를 비교할 수 있습니다.

#### 9.7.2 매핑 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Google Sheets Column → hand_clips Table Column                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────┐        ┌────────────────────────────────┐              │
│  │ A (Title)      │ ────→  │ title (VARCHAR 500)            │              │
│  ├────────────────┤        ├────────────────────────────────┤              │
│  │ B (Timecode)   │ ────→  │ timecode (VARCHAR)             │              │
│  ├────────────────┤        ├────────────────────────────────┤              │
│  │ C (Notes)      │ ────→  │ notes (TEXT)                   │              │
│  ├────────────────┤        ├────────────────────────────────┤              │
│  │ D (Grade)      │ ────→  │ hand_grade (★/★★/★★★)         │              │
│  ├────────────────┤        ├────────────────────────────────┤              │
│  │ Row #          │ ────→  │ sheet_row_number (INT)         │              │
│  ├────────────────┤        ├────────────────────────────────┤              │
│  │ Sheet ID       │ ────→  │ sheet_source (VARCHAR 50)      │              │
│  └────────────────┘        └────────────────────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 9.7.3 상세 매핑 테이블

| Sheets 컬럼 | DB 컬럼 | 변환 로직 | 비고 |
|-------------|---------|----------|------|
| A (Title) | title | 그대로 저장 | 최대 500자 |
| B (Timecode) | timecode | HH:MM:SS 또는 초단위 | |
| C (Notes) | notes | 그대로 저장 | TEXT |
| D (Grade) | hand_grade | ★ 개수로 정규화 | |
| Row # | sheet_row_number | 자동 설정 | 증분 동기화용 |
| Sheet ID | sheet_source | hand_analysis / hand_database | |

### 9.8 Video Files 검증 UI

#### 9.8.1 개요

NAS에서 동기화된 video_files 테이블 데이터를 브라우징하고 검증하는 UI입니다.
파싱된 메타데이터(project, season, event, episode)와 파일 상태를 확인할 수 있습니다.

#### 9.8.2 컴포넌트 구조

```
Sync.tsx (페이지)
├── Tab: 동기화 상태 (기존)
├── Tab: NAS 파일 (Issue #28)
│   └── VideoFilesInfiniteList.tsx
│       ├── FilterBar (프로젝트, 버전 타입, 스캔 상태)
│       ├── VideoFileCard (개별 파일)
│       └── InfiniteScrollTrigger
├── Tab: Sheets 데이터
│   └── HandClipsInfiniteList.tsx
│       ├── FilterBar (소스 필터)
│       ├── HandClipCard (개별 클립, DB 매핑 표시)
│       └── InfiniteScrollTrigger
```

#### 9.8.3 테이블 컬럼 정의

| 컬럼 | 너비 | 설명 | 필터 가능 |
|------|------|------|----------|
| 파일명/제목 | auto | display_title 우선, 없으면 file_name | No |
| 버전 | 100px | version_type (stream, clean, etc.) | Yes |
| 해상도 | 100px | resolution (1080p, 4K 등) | Yes |
| 상태 | 100px | scan_status (pending, scanned, failed) | Yes |
| 크기 | 100px | 포맷된 파일 크기 (GB/MB) | No |
| 숨김 | 80px | is_hidden 여부 | Yes |

### 9.9 무한 스크롤 컴포넌트 설계

#### 9.9.1 개요

IntersectionObserver API를 활용하여 스크롤 위치 감지 및 자동 데이터 로딩을 구현합니다.
TanStack Query의 `useInfiniteQuery`와 결합하여 효율적인 무한 스크롤 UX를 제공합니다.

#### 9.9.2 핵심 의존성

```json
{
  "@tanstack/react-query": "^5.x",
  "react-intersection-observer": "^9.x"
}
```

#### 9.9.3 InfiniteScrollList 공통 컴포넌트

```tsx
interface InfiniteScrollListProps<T> {
  queryKey: string[];
  fetchFn: (cursor: string | null) => Promise<CursorResponse<T>>;
  renderItem: (item: T) => React.ReactNode;
  emptyMessage?: string;
}

export function InfiniteScrollList<T>({
  queryKey,
  fetchFn,
  renderItem,
  emptyMessage = '데이터가 없습니다.'
}: InfiniteScrollListProps<T>) {
  // IntersectionObserver로 스크롤 감지
  const { ref: loadMoreRef, inView } = useInView();

  // useInfiniteQuery로 데이터 페칭
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery({
      queryKey,
      queryFn: ({ pageParam }) => fetchFn(pageParam),
      getNextPageParam: (lastPage) => lastPage.next_cursor,
      initialPageParam: null,
    });

  // 스크롤 시 자동 로딩
  useEffect(() => {
    if (inView && hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [inView, hasNextPage, isFetchingNextPage]);

  return (
    <div className="space-y-2">
      {data?.pages.flatMap(page => page.items).map(renderItem)}
      <div ref={loadMoreRef}>
        {isFetchingNextPage && <LoadingSpinner />}
      </div>
    </div>
  );
}
```

#### 9.9.4 성능 최적화

| 최적화 기법 | 설명 | 적용 |
|-------------|------|------|
| Virtual Scrolling | 대량 데이터 렌더링 최적화 | 1000+ items |
| React.memo | 불필요한 리렌더링 방지 | Row 컴포넌트 |
| rootMargin | 미리 로딩 (100px 전) | IntersectionObserver |
| Query Cache | 중복 요청 방지 | staleTime 30s |

---

## 10. 참조

| 문서 | 설명 |
|------|------|
| [01_DATABASE_SCHEMA.md](./01_DATABASE_SCHEMA.md) | DB 스키마 |
| [03_FILE_PARSER.md](./03_FILE_PARSER.md) | 파일명 파서 |
| [04_DOCKER_DEPLOYMENT.md](./04_DOCKER_DEPLOYMENT.md) | Docker 배포 |

---

**문서 버전**: 1.4.0
**작성일**: 2025-12-09
**수정일**: 2025-12-10
**상태**: Updated v1.4.0 - NAS 폴더 하이어라키 전체 표시, DB 매핑 다이어그램 추가

### 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.4.0 | 2025-12-10 | Issue #28 수정: max_depth 5→15 (전체 하이어라키), DbMappingDiagram 컴포넌트 추가 |
| 1.3.0 | 2025-12-10 | Issue #28: Section 9.6-9.9 추가 (Cursor 페이지네이션 API, DB 매핑 정보, Video Files UI, 무한 스크롤 컴포넌트) |
| 1.2.0 | 2025-12-10 | Section 9 Hand Clips 검증 대시보드 설계 추가 (API, Frontend 컴포넌트, 검증 URL) |
| 1.1.0 | 2025-12-09 | #6 빈 파일 목록 체크 추가, #10 Episode 매핑 플로우, #12 배치 처리 로직, #13 BULK INSERT 최적화, conflict_status 활용 |
| 1.0.0 | 2025-12-09 | 초기 버전 |
