# Google Sheets 상세 분석 및 DB 설계 권장사항

> **분석일**: 2025-12-09
> **목적**: PRD에 명시된 Google Sheets 데이터를 분석하여 최적의 DB 구조 설계

---

## 1. Google Sheets 데이터 분석

### 1.1 Sheet 1: 핸드 분석 시트 (WSOP Circuit)

**시트 ID**: `1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4`

| # | 컬럼명 | 데이터 타입 | 샘플 값 | DB 매핑 권장 |
|---|--------|----------|--------|-------------|
| 1 | File No. | INTEGER | 1, 2, 3... | `hand_clips.clip_number` |
| 2 | File Name | VARCHAR(500) | "2024 WSOP Circuit Los Angeles - House Warming..." | `episodes.title` 매칭용 |
| 3 | Nas Folder Link | TEXT | `\\10.10.100.122\docker\GGPNAs\ARCHIVE\...` | `video_files.file_path` |
| 4 | In | TIME | "6:58:55", "7:03:00" | `hand_clips.timecode_in` |
| 5 | Out | TIME | "7:00:47", "7:06:10" | `hand_clips.timecode_out` |
| 6 | Hand Grade | VARCHAR(10) | "★", "★★", "★★★" | `hand_clips.hand_grade` |
| 7 | Winner | VARCHAR(50) | "JJ", "QQ", "AA", "A9s" | `hand_clips.winner_hand` |
| 8 | Hands | VARCHAR(100) | "88 vs JJ", "AKo vs KK vs QQ" | `hand_clips.hands_involved` |
| 9-11 | Tag (Player) 1~3 | VARCHAR(100) | "Christina Gollins", "baby shark" | `hand_clip_players` (N:N) |
| 12-19 | Tag (Poker Play) 1~7 | VARCHAR(50) | "Nice Fold", "Preflop All-in", "Cooler" | `hand_clip_tags` (N:N) |
| 20-21 | Tag (Emotion) 1~2 | VARCHAR(50) | "Stressed", "Excitement", "Laughing" | `hand_clip_tags` (N:N) |

**특성**:
- 다중 태그 시스템 (Player 3개, PokerPlay 7개, Emotion 2개)
- 많은 셀이 비어있음 → nullable 컬럼 필요
- 타임코드 형식: `H:MM:SS` 또는 `HH:MM:SS`

---

### 1.2 Sheet 2: 핸드 데이터베이스 (통합)

**시트 ID**: `1pUMPKe-OsKc-Xd8lH1cP9ctJO4hj3keXY5RwNFp2Mtk`

| # | 컬럼명 | 데이터 타입 | 샘플 값 | DB 매핑 권장 |
|---|--------|----------|--------|-------------|
| 1 | id | UUID | `4fcb98f2-ee5b-11ef-9be4-faa8f6b7d111` | `hand_clips.id` |
| 2 | title | VARCHAR(500) | `7-wsop-2024-be-ev-12-1500-nlh-ft-Fan-doubles-KK-vs-Yea-QQs` | `hand_clips.title` |
| 3 | time_start_ms | INTEGER | (대부분 비어있음) | `hand_clips.start_seconds` * 1000 |
| 4 | time_end_ms | INTEGER | (대부분 비어있음) | `hand_clips.end_seconds` * 1000 |
| 5 | Description | TEXT | "COOLER HAND PREFLOP ALL IN FAN vs YEA KK vs QQ" | `hand_clips.description` |
| 6 | ProjectName | VARCHAR(50) | `WSOP`, `WSOP PARADISE` | `projects.code` |
| 7 | Year_ | INTEGER | `2024` | `seasons.year` |
| 8 | Location | VARCHAR(100) | `LAS VEGAS`, `BAHAMAS` | `seasons.location` |
| 9 | Venue | VARCHAR(200) | `$1,500 NLH 6-MAX` | `events.name` |
| 10 | EpisodeEvent | VARCHAR(200) | `$1,500 NLH 6-MAX` | `events.name` 중복 |
| 11 | Source | VARCHAR(20) | `PGM`, `Clean` | `video_files.version_type` |
| 12 | PlayersTags | TEXT | `Phil Hellmuth, Daniel Negreanu` | 쉼표 구분 → `hand_clip_players` |
| 13 | HandGrade | VARCHAR(10) | `★★★` | `hand_clips.hand_grade` |
| 14 | HANDTag | VARCHAR(100) | `QQ vs KK` | `hand_clips.hands_involved` |
| 15 | Emotion | VARCHAR(100) | `excitement, relief, pain` | 쉼표 구분 → `tags` (emotion) |
| 16 | GameType | VARCHAR(50) | `NLHE`, `PLO` | `events.game_type` |
| 17 | PokerPlayTags | TEXT | `Cooler, Bluff, BadBeat` | 쉼표 구분 → `tags` (poker_play) |
| 18 | RUNOUTTag | VARCHAR(50) | `river, turn` | `tags` (runout) |
| 19 | PostFlop | TEXT | 플롭 후 액션 설명 | `hand_clips.description` 보완 |
| 20 | All-in | VARCHAR(50) | 올인 여부/유형 | `tags` (poker_play) |
| 21 | EPICHAND | VARCHAR(100) | `Straight Flush, Quads` | `tags` (epic_hand) |
| 22 | Adjective | VARCHAR(100) | `brutal, incredible, insane` | `tags` (adjective) |

**특성**:
- UUID 기반 ID 사용
- 다중 값 컬럼이 쉼표로 구분됨 → 정규화 필요
- 70-80% 데이터가 부분적으로 채워짐 → nullable 허용

---

## 2. 데이터 정규화 분석

### 2.1 태그 카테고리 통합

두 시트의 태그를 통합하면 **6개 카테고리**:

| 카테고리 | 출처 | 샘플 값 | DB 테이블 |
|----------|------|--------|----------|
| `poker_play` | Sheet 1/2 | Preflop All-in, Cooler, Bad Beat, Bluff, Hero Call, Suckout | `tags` |
| `emotion` | Sheet 1/2 | Stressed, Excitement, Relief, Pain, Laughing | `tags` |
| `epic_hand` | Sheet 2 | Royal Flush, Straight Flush, Quads, Full House | `tags` |
| `runout` | Sheet 2 | runner runner, 1out, dirty, river, turn | `tags` |
| `adjective` | Sheet 2 | brutal, incredible, insane, sick | `tags` |
| `hand_grade` | Sheet 1/2 | ★, ★★, ★★★ | `hand_clips.hand_grade` (직접 저장) |

### 2.2 엔티티 관계 분석

```
Sheet 데이터         →     정규화된 DB 구조
─────────────────────────────────────────────

ProjectName          →     projects (1)
Year_ + Location     →     seasons (N per project)
Venue + EpisodeEvent →     events (N per season)
File Name            →     episodes (N per event)
Nas Folder Link      →     video_files (N per episode)
id + title + In/Out  →     hand_clips (N per video_file)
PlayersTags          →     hand_clip_players (N:N)
PokerPlayTags + ...  →     hand_clip_tags (N:N) → tags
```

---

## 3. DB 스키마 설계 권장사항

### 3.1 PRD 스키마 vs 권장 수정사항

| PRD 스키마 | 권장 수정 | 이유 |
|-----------|----------|------|
| `Season.venue` | **제거** → `Event`로 이동 | Venue는 시즌이 아닌 이벤트 속성 |
| `Episode.table_type` | 유지 + enum 정의 | preliminary/day1/day2/final_table/heads_up |
| `VideoFile.version_type` | 유지 + **enum 확장** | clean/mastered/stream/subclip/**pgm** |
| `Tag.category` | **6개 카테고리** 확정 | poker_play, emotion, epic_hand, runout, adjective, hand_grade |
| `HandClip.hand_grade` | **직접 저장** (정규화 X) | ★~★★★은 고정값이므로 join 불필요 |

### 3.2 신규 테이블 권장

#### `google_sheet_sync` (동기화 상태 추적)

```sql
CREATE TABLE google_sheet_sync (
    id UUID PRIMARY KEY,
    sheet_id VARCHAR(200) NOT NULL,        -- Google Sheet ID
    sheet_name VARCHAR(200),               -- 시트명/탭명
    entity_type VARCHAR(50) NOT NULL,      -- hand_clip, event, player
    last_synced_at TIMESTAMP,
    sync_status VARCHAR(20) DEFAULT 'pending',  -- success/failed/pending
    row_count INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 인덱스 권장

```sql
-- 핸드 클립 검색 최적화
CREATE INDEX idx_hand_clips_timecode ON hand_clips(video_file_id, start_seconds);
CREATE INDEX idx_hand_clips_grade ON hand_clips(hand_grade);

-- 태그 기반 검색
CREATE INDEX idx_hand_clip_tags_tag ON hand_clip_tags(tag_id);
CREATE INDEX idx_tags_category ON tags(category);

-- 플레이어 검색
CREATE INDEX idx_hand_clip_players_player ON hand_clip_players(player_id);
CREATE INDEX idx_players_name ON players(name);
```

---

## 4. 기존 archive-analyzer와의 통합 전략

### 4.1 통합 옵션

| 옵션 | 장점 | 단점 | 권장 |
|------|------|------|------|
| **A: pokervod.db 확장** | 기존 V3.0 스키마 재사용, 검증된 구조 | db_architecture 프로젝트와 분리 | △ |
| **B: 신규 DB 생성** | 깔끔한 시작, PRD 스키마 그대로 적용 | 중복 노력, 마이그레이션 필요 | △ |
| **C: 하이브리드** | pokervod.db의 core 테이블 사용 + 신규 테이블 추가 | 복잡성 증가 | **✅** |

### 4.2 권장: 하이브리드 접근

1. **기존 재사용** (pokervod.db):
   - `catalogs` → `projects` (rename 또는 alias)
   - `series` → `seasons`
   - `contents` → `episodes`
   - `files` → `video_files`
   - `tags`, `content_tags`
   - `players`, `content_players`

2. **신규 추가**:
   - `events` (PRD 명세 따름)
   - `hand_clips` (PRD 명세 따름)
   - `hand_clip_tags`, `hand_clip_players`
   - `event_results`, `bracelets`
   - `google_sheet_sync`

### 4.3 테이블 매핑

```
PRD 스키마           →     pokervod.db 기존 테이블
───────────────────────────────────────────────
Project              →     catalogs (확장)
Season               →     series (확장: location, venue 추가)
Event                →     **신규**
Episode              →     contents (확장)
VideoFile            →     files (확장)
Player               →     players (확장)
Tag                  →     tags (category 추가)
HandClip             →     **신규** (기존 hands 대체)
HandClip_Tag         →     content_tags 패턴 활용
HandClip_Player      →     content_players 패턴 활용
EventResult          →     **신규**
Bracelet             →     **신규**
GoogleSheetSync      →     **신규**
```

---

## 5. 구현 로드맵

### Phase 1: 스키마 확장
1. pokervod.db에 누락 컬럼 추가 (location, venue 등)
2. `events` 테이블 생성
3. `hand_clips` 테이블 생성 (기존 `hands` 대체)
4. 태그 카테고리 6개 확정 및 시드 데이터 입력

### Phase 2: 동기화 구현
1. `google_sheet_sync` 테이블 생성
2. 기존 `sheets_sync.py` 로직 참조
3. Sheet 1 → hand_clips 매핑
4. Sheet 2 → hand_clips + tags 매핑

### Phase 3: 검증
1. 데이터 무결성 검사
2. 중복 데이터 정리
3. 인덱스 성능 테스트

---

## 6. 결론

### 권장 사항 요약

| 항목 | 권장 |
|------|------|
| **DB 선택** | pokervod.db 확장 (하이브리드) |
| **태그 카테고리** | 6개 (poker_play, emotion, epic_hand, runout, adjective, hand_grade) |
| **hand_grade 저장** | `hand_clips` 테이블에 직접 저장 (정규화 X) |
| **동기화 라이브러리** | gspread (기존 archive-analyzer 구현 재사용) |
| **신규 테이블** | events, hand_clips, hand_clip_tags, hand_clip_players, event_results, bracelets, google_sheet_sync |

### 다음 단계

1. **승인 필요**: 하이브리드 접근법 사용 여부
2. **결정 필요**: pokervod.db vs 신규 DB
3. **확인 필요**: PRD의 PostgreSQL 계획 유지 vs SQLite 유지

---

**문서 버전**: 1.0
**작성일**: 2025-12-09
