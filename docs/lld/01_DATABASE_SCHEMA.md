# LLD 01: Database Schema Design

> **버전**: 1.0.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09

---

## 1. 개요

PostgreSQL 15 기반의 GGP Poker Video Catalog 데이터베이스 스키마 상세 설계 문서입니다.

### 1.1 설계 원칙

| 원칙 | 설명 |
|------|------|
| **UUID 기본키** | 모든 테이블은 UUID를 기본키로 사용 (분산 환경 대비) |
| **Soft Delete** | 물리 삭제 대신 `deleted_at` 컬럼 사용 |
| **Audit Trail** | `created_at`, `updated_at` 자동 관리 |
| **정규화** | 3NF 준수, 다대다 관계는 연결 테이블 사용 |
| **Enum 일관성** | CHECK 제약조건으로 유효값 강제 |

### 1.2 테이블 목록

```
Core Tables (12개)
├── projects              # 프로젝트 (WSOP, HCL, GGMillions 등)
├── seasons               # 시즌 (연도별)
├── events                # 이벤트 (토너먼트, 캐시게임)
├── episodes              # 에피소드 (개별 영상)
├── video_files           # 비디오 파일
├── players               # 플레이어
├── tags                  # 태그 (포커 플레이, 감정 등)
├── hand_clips            # 핸드 클립
├── hand_clip_tags        # 핸드클립-태그 연결
├── hand_clip_players     # 핸드클립-플레이어 연결
├── event_results         # 이벤트 결과
└── bracelets             # 브레이슬릿 (WSOP)

Sync Tables (4개)
├── google_sheet_sync     # 구글 시트 동기화 상태
├── nas_scan_checkpoints  # NAS 스캔 체크포인트
├── sync_logs             # 동기화 로그
└── change_history        # 변경 이력
```

---

## 2. DDL (Data Definition Language)

### 2.1 Extension 및 설정

```sql
-- UUID 생성 함수
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 타임존 설정
SET timezone = 'Asia/Seoul';

-- 기본 스키마 생성
CREATE SCHEMA IF NOT EXISTS pokervod;
SET search_path TO pokervod, public;
```

### 2.2 Core Tables

#### 2.2.1 projects

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    nas_base_path VARCHAR(500),
    filename_pattern VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT chk_project_code CHECK (
        code IN ('WSOP', 'HCL', 'GGMILLIONS', 'MPP', 'PAD', 'GOG', 'OTHER')
    )
);

CREATE INDEX idx_projects_code ON projects(code);
CREATE INDEX idx_projects_active ON projects(is_active) WHERE is_active = true;

COMMENT ON TABLE projects IS '프로젝트 (포커 시리즈)';
COMMENT ON COLUMN projects.code IS '프로젝트 코드 (WSOP, HCL, GGMILLIONS, MPP, PAD, GOG, OTHER)';
COMMENT ON COLUMN projects.filename_pattern IS '파일명 파싱용 정규식 패턴';
```

#### 2.2.2 seasons

```sql
CREATE TABLE seasons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    name VARCHAR(200) NOT NULL,
    location VARCHAR(200),
    sub_category VARCHAR(50),
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT chk_season_sub_category CHECK (
        sub_category IS NULL OR sub_category IN (
            'ARCHIVE', 'BRACELET_LV', 'BRACELET_EU', 'BRACELET_PARA',
            'CIRCUIT', 'SUPER_CIRCUIT'
        )
    ),
    CONSTRAINT chk_season_status CHECK (
        status IN ('active', 'completed', 'upcoming')
    ),
    CONSTRAINT chk_season_dates CHECK (
        start_date IS NULL OR end_date IS NULL OR start_date <= end_date
    )
);

CREATE INDEX idx_seasons_project ON seasons(project_id);
CREATE INDEX idx_seasons_year ON seasons(year);
CREATE INDEX idx_seasons_sub_category ON seasons(sub_category) WHERE sub_category IS NOT NULL;
CREATE UNIQUE INDEX idx_seasons_unique ON seasons(project_id, year, COALESCE(sub_category, ''));

COMMENT ON TABLE seasons IS '시즌 (연도별 프로젝트 인스턴스)';
COMMENT ON COLUMN seasons.sub_category IS 'WSOP 전용: ARCHIVE, BRACELET_LV, BRACELET_EU, BRACELET_PARA, CIRCUIT, SUPER_CIRCUIT';
```

#### 2.2.3 events

```sql
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    season_id UUID NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    event_number INTEGER,
    name VARCHAR(500) NOT NULL,
    name_short VARCHAR(100),
    event_type VARCHAR(50),
    game_type VARCHAR(50),
    buy_in DECIMAL(10,2),
    gtd_amount DECIMAL(15,2),
    venue VARCHAR(200),
    entry_count INTEGER,
    prize_pool DECIMAL(15,2),
    start_date DATE,
    end_date DATE,
    total_days INTEGER,
    status VARCHAR(20) DEFAULT 'upcoming',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT chk_event_type CHECK (
        event_type IN (
            'bracelet', 'circuit', 'super_circuit', 'high_roller',
            'super_high_roller', 'cash_game', 'tv_series',
            'mystery_bounty', 'main_event'
        )
    ),
    CONSTRAINT chk_event_game_type CHECK (
        game_type IS NULL OR game_type IN (
            'NLHE', 'PLO', 'PLO8', 'Mixed', 'Stud', 'Razz',
            'HORSE', '2-7TD', '2-7SD', 'Badugi', 'OE', 'NLO8'
        )
    ),
    CONSTRAINT chk_event_status CHECK (
        status IN ('upcoming', 'in_progress', 'completed')
    ),
    CONSTRAINT chk_event_buy_in CHECK (buy_in IS NULL OR buy_in >= 0),
    CONSTRAINT chk_event_gtd CHECK (gtd_amount IS NULL OR gtd_amount >= 0)
);

CREATE INDEX idx_events_season ON events(season_id);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_game_type ON events(game_type);
CREATE INDEX idx_events_buy_in ON events(buy_in);
CREATE INDEX idx_events_status ON events(status);

COMMENT ON TABLE events IS '이벤트 (토너먼트, 캐시게임, TV 시리즈)';
COMMENT ON COLUMN events.gtd_amount IS 'GTD 보장 상금 (MPP, Circuit 등)';
COMMENT ON COLUMN events.venue IS '개최 장소 (카지노명)';
```

#### 2.2.4 episodes

```sql
CREATE TABLE episodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    episode_number INTEGER,
    day_number INTEGER,
    part_number INTEGER,
    title VARCHAR(500),
    episode_type VARCHAR(50),
    table_type VARCHAR(50),
    duration_seconds INTEGER,
    air_date DATE,
    synopsis TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT chk_episode_type CHECK (
        episode_type IS NULL OR episode_type IN (
            'full', 'highlight', 'recap', 'interview', 'subclip'
        )
    ),
    CONSTRAINT chk_table_type CHECK (
        table_type IS NULL OR table_type IN (
            'preliminary', 'day1', 'day2', 'day3', 'final_table', 'heads_up'
        )
    ),
    CONSTRAINT chk_duration CHECK (duration_seconds IS NULL OR duration_seconds > 0)
);

CREATE INDEX idx_episodes_event ON episodes(event_id);
CREATE INDEX idx_episodes_type ON episodes(episode_type);
CREATE INDEX idx_episodes_table_type ON episodes(table_type);
CREATE INDEX idx_episodes_day ON episodes(day_number);

COMMENT ON TABLE episodes IS '에피소드 (개별 영상 단위)';
COMMENT ON COLUMN episodes.table_type IS '테이블 단계: preliminary, day1, day2, day3, final_table, heads_up';
```

#### 2.2.5 video_files

```sql
CREATE TABLE video_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    episode_id UUID REFERENCES episodes(id) ON DELETE SET NULL,
    file_path VARCHAR(1000) NOT NULL UNIQUE,
    file_name VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT,
    file_format VARCHAR(20),
    resolution VARCHAR(20),
    video_codec VARCHAR(50),
    audio_codec VARCHAR(50),
    bitrate_kbps INTEGER,
    duration_seconds INTEGER,
    version_type VARCHAR(20),
    is_original BOOLEAN DEFAULT false,
    checksum VARCHAR(64),
    file_mtime TIMESTAMP WITH TIME ZONE,
    scan_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT chk_file_format CHECK (
        file_format IS NULL OR file_format IN ('mp4', 'mov', 'mxf', 'avi', 'mkv')
    ),
    CONSTRAINT chk_version_type CHECK (
        version_type IS NULL OR version_type IN (
            'clean', 'mastered', 'stream', 'subclip', 'final_edit',
            'nobug', 'pgm', 'generic', 'hires'
        )
    ),
    CONSTRAINT chk_scan_status CHECK (
        scan_status IN ('pending', 'scanned', 'failed', 'deleted')
    ),
    CONSTRAINT chk_file_size CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0)
);

CREATE INDEX idx_video_files_episode ON video_files(episode_id);
CREATE INDEX idx_video_files_path ON video_files(file_path);
CREATE INDEX idx_video_files_format ON video_files(file_format);
CREATE INDEX idx_video_files_version ON video_files(version_type);
CREATE INDEX idx_video_files_mtime ON video_files(file_mtime);
CREATE INDEX idx_video_files_scan_status ON video_files(scan_status);

COMMENT ON TABLE video_files IS '비디오 파일 메타데이터';
COMMENT ON COLUMN video_files.version_type IS 'clean, mastered, stream, subclip, final_edit, nobug, pgm, generic, hires';
COMMENT ON COLUMN video_files.file_mtime IS 'NAS 파일 수정시간 (증분 스캔용)';
```

#### 2.2.6 players

```sql
CREATE TABLE players (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    name_display VARCHAR(200),
    nationality VARCHAR(100),
    hendon_mob_id VARCHAR(50),
    total_live_earnings DECIMAL(15,2),
    wsop_bracelets INTEGER DEFAULT 0,
    profile_image_url VARCHAR(1000),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT chk_bracelets CHECK (wsop_bracelets >= 0),
    CONSTRAINT chk_earnings CHECK (total_live_earnings IS NULL OR total_live_earnings >= 0)
);

CREATE INDEX idx_players_name ON players(name);
CREATE INDEX idx_players_name_display ON players(name_display);
CREATE INDEX idx_players_hendon_mob ON players(hendon_mob_id) WHERE hendon_mob_id IS NOT NULL;
CREATE INDEX idx_players_bracelets ON players(wsop_bracelets) WHERE wsop_bracelets > 0;

COMMENT ON TABLE players IS '포커 플레이어';
COMMENT ON COLUMN players.hendon_mob_id IS 'Hendon Mob 플레이어 ID (외부 참조)';
```

#### 2.2.7 tags

```sql
CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_display VARCHAR(100),
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_tag_category CHECK (
        category IN ('poker_play', 'emotion', 'epic_hand', 'runout', 'adjective')
    ),
    CONSTRAINT uq_tag_category_name UNIQUE (category, name)
);

CREATE INDEX idx_tags_category ON tags(category);
CREATE INDEX idx_tags_name ON tags(name);
CREATE INDEX idx_tags_sort ON tags(category, sort_order);

COMMENT ON TABLE tags IS '태그 (포커 플레이, 감정, 에픽 핸드 등)';
COMMENT ON COLUMN tags.category IS 'poker_play, emotion, epic_hand, runout, adjective';
```

#### 2.2.8 hand_clips

```sql
CREATE TABLE hand_clips (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    episode_id UUID REFERENCES episodes(id) ON DELETE SET NULL,
    video_file_id UUID REFERENCES video_files(id) ON DELETE SET NULL,
    clip_number INTEGER,
    title VARCHAR(500),
    timecode_in VARCHAR(20),
    timecode_out VARCHAR(20),
    start_seconds INTEGER,
    end_seconds INTEGER,
    winner_hand VARCHAR(100),
    hands_involved VARCHAR(200),
    description TEXT,
    hand_grade VARCHAR(10),
    sheet_row_number INTEGER,
    sheet_source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT chk_hand_grade CHECK (
        hand_grade IS NULL OR hand_grade IN ('★', '★★', '★★★')
    ),
    CONSTRAINT chk_timecode CHECK (
        start_seconds IS NULL OR end_seconds IS NULL OR start_seconds < end_seconds
    ),
    CONSTRAINT chk_sheet_source CHECK (
        sheet_source IS NULL OR sheet_source IN ('hand_analysis', 'hand_database')
    )
);

CREATE INDEX idx_hand_clips_episode ON hand_clips(episode_id);
CREATE INDEX idx_hand_clips_video ON hand_clips(video_file_id);
CREATE INDEX idx_hand_clips_grade ON hand_clips(hand_grade);
CREATE INDEX idx_hand_clips_timecode ON hand_clips(video_file_id, start_seconds);
CREATE INDEX idx_hand_clips_sheet_row ON hand_clips(sheet_source, sheet_row_number);

COMMENT ON TABLE hand_clips IS '핸드 클립 (타임코드 기반 세그먼트)';
COMMENT ON COLUMN hand_clips.hand_grade IS '핸드 등급: ★, ★★, ★★★';
COMMENT ON COLUMN hand_clips.sheet_row_number IS '원본 Google Sheet 행 번호 (동기화용)';
```

#### 2.2.9 hand_clip_tags

```sql
CREATE TABLE hand_clip_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hand_clip_id UUID NOT NULL REFERENCES hand_clips(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    tag_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_hand_clip_tag UNIQUE (hand_clip_id, tag_id)
);

CREATE INDEX idx_hand_clip_tags_clip ON hand_clip_tags(hand_clip_id);
CREATE INDEX idx_hand_clip_tags_tag ON hand_clip_tags(tag_id);

COMMENT ON TABLE hand_clip_tags IS '핸드클립-태그 연결 (N:M)';
```

#### 2.2.10 hand_clip_players

```sql
CREATE TABLE hand_clip_players (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hand_clip_id UUID NOT NULL REFERENCES hand_clips(id) ON DELETE CASCADE,
    player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    player_order INTEGER DEFAULT 0,
    role VARCHAR(20),
    hole_cards VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_player_role CHECK (
        role IS NULL OR role IN ('winner', 'loser', 'involved')
    ),
    CONSTRAINT uq_hand_clip_player UNIQUE (hand_clip_id, player_id)
);

CREATE INDEX idx_hand_clip_players_clip ON hand_clip_players(hand_clip_id);
CREATE INDEX idx_hand_clip_players_player ON hand_clip_players(player_id);
CREATE INDEX idx_hand_clip_players_role ON hand_clip_players(role);

COMMENT ON TABLE hand_clip_players IS '핸드클립-플레이어 연결 (N:M)';
COMMENT ON COLUMN hand_clip_players.hole_cards IS '홀카드 표기 (예: AsKs, QhQd)';
```

#### 2.2.11 event_results

```sql
CREATE TABLE event_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    finish_position INTEGER NOT NULL,
    prize_amount DECIMAL(15,2),
    is_winner BOOLEAN DEFAULT false,
    is_final_table BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_position CHECK (finish_position > 0),
    CONSTRAINT chk_prize CHECK (prize_amount IS NULL OR prize_amount >= 0),
    CONSTRAINT uq_event_player_position UNIQUE (event_id, player_id)
);

CREATE INDEX idx_event_results_event ON event_results(event_id);
CREATE INDEX idx_event_results_player ON event_results(player_id);
CREATE INDEX idx_event_results_winner ON event_results(event_id) WHERE is_winner = true;
CREATE INDEX idx_event_results_final_table ON event_results(event_id) WHERE is_final_table = true;

COMMENT ON TABLE event_results IS '이벤트 결과 (순위, 상금)';
```

#### 2.2.12 bracelets

```sql
CREATE TABLE bracelets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    bracelet_number INTEGER NOT NULL,
    prize_amount DECIMAL(15,2),
    win_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_bracelet_number CHECK (bracelet_number > 0),
    CONSTRAINT uq_bracelet_event UNIQUE (event_id)
);

CREATE INDEX idx_bracelets_player ON bracelets(player_id);
CREATE INDEX idx_bracelets_event ON bracelets(event_id);

COMMENT ON TABLE bracelets IS 'WSOP 브레이슬릿 기록';
```

### 2.3 Sync Tables

#### 2.3.1 google_sheet_sync

```sql
CREATE TABLE google_sheet_sync (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sheet_id VARCHAR(200) NOT NULL,
    sheet_name VARCHAR(200),
    sheet_url VARCHAR(500),
    entity_type VARCHAR(50) NOT NULL,
    last_synced_at TIMESTAMP WITH TIME ZONE,
    last_row_synced INTEGER DEFAULT 0,
    sync_status VARCHAR(20) DEFAULT 'pending',
    row_count INTEGER DEFAULT 0,
    new_rows_count INTEGER DEFAULT 0,
    updated_rows_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_entity_type CHECK (
        entity_type IN ('hand_clip', 'event', 'player')
    ),
    CONSTRAINT chk_sync_status CHECK (
        sync_status IN ('success', 'failed', 'pending', 'running')
    ),
    CONSTRAINT uq_sheet_entity UNIQUE (sheet_id, entity_type)
);

CREATE INDEX idx_sheet_sync_status ON google_sheet_sync(sync_status);
CREATE INDEX idx_sheet_sync_last ON google_sheet_sync(last_synced_at);

COMMENT ON TABLE google_sheet_sync IS 'Google Sheet 동기화 상태 추적';
COMMENT ON COLUMN google_sheet_sync.last_row_synced IS '마지막 동기화된 행 번호 (증분 동기화용)';
```

#### 2.3.2 nas_scan_checkpoints

```sql
CREATE TABLE nas_scan_checkpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_code VARCHAR(20) NOT NULL,
    scan_path VARCHAR(1000) NOT NULL,
    last_scanned_at TIMESTAMP WITH TIME ZONE,
    last_file_mtime TIMESTAMP WITH TIME ZONE,
    total_files INTEGER DEFAULT 0,
    new_files_count INTEGER DEFAULT 0,
    scan_status VARCHAR(20) DEFAULT 'pending',
    scan_duration_sec INTEGER,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_project_code CHECK (
        project_code IN ('WSOP', 'HCL', 'GGMILLIONS', 'MPP', 'PAD', 'GOG', 'OTHER', 'ALL')
    ),
    CONSTRAINT chk_scan_status CHECK (
        scan_status IN ('success', 'failed', 'running', 'pending')
    ),
    CONSTRAINT uq_checkpoint_path UNIQUE (project_code, scan_path)
);

CREATE INDEX idx_checkpoint_project ON nas_scan_checkpoints(project_code);
CREATE INDEX idx_checkpoint_status ON nas_scan_checkpoints(scan_status);
CREATE INDEX idx_checkpoint_mtime ON nas_scan_checkpoints(last_file_mtime);

COMMENT ON TABLE nas_scan_checkpoints IS 'NAS 스캔 체크포인트 (증분 스캔용)';
COMMENT ON COLUMN nas_scan_checkpoints.last_file_mtime IS '마지막 파일 수정시간 (mtime 기반 증분 스캔)';
```

#### 2.3.3 sync_logs

```sql
CREATE TABLE sync_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sync_type VARCHAR(20) NOT NULL,
    source VARCHAR(100),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL,
    records_processed INTEGER DEFAULT 0,
    records_created INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_details JSONB,

    CONSTRAINT chk_sync_type CHECK (
        sync_type IN ('nas_scan', 'sheet_sync', 'full_sync', 'validation')
    ),
    CONSTRAINT chk_status CHECK (
        status IN ('running', 'success', 'failed', 'partial')
    )
);

CREATE INDEX idx_sync_logs_type ON sync_logs(sync_type);
CREATE INDEX idx_sync_logs_status ON sync_logs(status);
CREATE INDEX idx_sync_logs_started ON sync_logs(started_at DESC);

COMMENT ON TABLE sync_logs IS '동기화 작업 로그';
COMMENT ON COLUMN sync_logs.error_details IS '에러 상세 (JSON 형식)';
```

#### 2.3.4 change_history

```sql
CREATE TABLE change_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    changed_fields JSONB,
    old_values JSONB,
    new_values JSONB,
    change_source VARCHAR(50),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(100),

    CONSTRAINT chk_entity_type CHECK (
        entity_type IN (
            'project', 'season', 'event', 'episode', 'video_file',
            'player', 'tag', 'hand_clip'
        )
    ),
    CONSTRAINT chk_change_type CHECK (
        change_type IN ('create', 'update', 'delete')
    ),
    CONSTRAINT chk_change_source CHECK (
        change_source IS NULL OR change_source IN (
            'nas_scan', 'sheet_sync', 'manual', 'api', 'migration'
        )
    )
);

CREATE INDEX idx_change_history_entity ON change_history(entity_type, entity_id);
CREATE INDEX idx_change_history_type ON change_history(change_type);
CREATE INDEX idx_change_history_source ON change_history(change_source);
CREATE INDEX idx_change_history_time ON change_history(changed_at DESC);

COMMENT ON TABLE change_history IS '데이터 변경 이력 (Audit Trail)';
```

---

## 3. Triggers & Functions

### 3.1 자동 updated_at 갱신

```sql
-- 트리거 함수
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 각 테이블에 트리거 적용
CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_seasons_updated_at
    BEFORE UPDATE ON seasons
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_events_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_episodes_updated_at
    BEFORE UPDATE ON episodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_video_files_updated_at
    BEFORE UPDATE ON video_files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_players_updated_at
    BEFORE UPDATE ON players
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_hand_clips_updated_at
    BEFORE UPDATE ON hand_clips
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 3.2 변경 이력 자동 기록

```sql
-- 변경 이력 기록 함수
CREATE OR REPLACE FUNCTION record_change_history()
RETURNS TRIGGER AS $$
DECLARE
    v_entity_type VARCHAR(50);
    v_change_type VARCHAR(20);
    v_old_values JSONB;
    v_new_values JSONB;
BEGIN
    -- 테이블명에서 entity_type 추출
    v_entity_type = TG_TABLE_NAME;
    IF v_entity_type = 'video_files' THEN v_entity_type = 'video_file'; END IF;
    IF v_entity_type = 'hand_clips' THEN v_entity_type = 'hand_clip'; END IF;

    IF TG_OP = 'INSERT' THEN
        v_change_type = 'create';
        v_new_values = to_jsonb(NEW);
        INSERT INTO change_history (entity_type, entity_id, change_type, new_values, change_source)
        VALUES (v_entity_type, NEW.id, v_change_type, v_new_values, current_setting('app.change_source', true));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        v_change_type = 'update';
        v_old_values = to_jsonb(OLD);
        v_new_values = to_jsonb(NEW);
        INSERT INTO change_history (entity_type, entity_id, change_type, old_values, new_values, change_source)
        VALUES (v_entity_type, NEW.id, v_change_type, v_old_values, v_new_values, current_setting('app.change_source', true));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        v_change_type = 'delete';
        v_old_values = to_jsonb(OLD);
        INSERT INTO change_history (entity_type, entity_id, change_type, old_values, change_source)
        VALUES (v_entity_type, OLD.id, v_change_type, v_old_values, current_setting('app.change_source', true));
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 주요 테이블에 트리거 적용
CREATE TRIGGER record_video_files_history
    AFTER INSERT OR UPDATE OR DELETE ON video_files
    FOR EACH ROW EXECUTE FUNCTION record_change_history();

CREATE TRIGGER record_hand_clips_history
    AFTER INSERT OR UPDATE OR DELETE ON hand_clips
    FOR EACH ROW EXECUTE FUNCTION record_change_history();
```

### 3.3 타임코드 → 초 변환

```sql
-- 타임코드(HH:MM:SS) → 초 변환 함수
CREATE OR REPLACE FUNCTION timecode_to_seconds(timecode VARCHAR)
RETURNS INTEGER AS $$
DECLARE
    parts TEXT[];
    hours INTEGER;
    minutes INTEGER;
    seconds INTEGER;
BEGIN
    IF timecode IS NULL OR timecode = '' THEN
        RETURN NULL;
    END IF;

    parts = string_to_array(timecode, ':');

    IF array_length(parts, 1) = 3 THEN
        hours = parts[1]::INTEGER;
        minutes = parts[2]::INTEGER;
        seconds = parts[3]::INTEGER;
        RETURN hours * 3600 + minutes * 60 + seconds;
    ELSIF array_length(parts, 1) = 2 THEN
        minutes = parts[1]::INTEGER;
        seconds = parts[2]::INTEGER;
        RETURN minutes * 60 + seconds;
    ELSE
        RETURN NULL;
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 초 → 타임코드 변환 함수
CREATE OR REPLACE FUNCTION seconds_to_timecode(total_seconds INTEGER)
RETURNS VARCHAR AS $$
DECLARE
    hours INTEGER;
    minutes INTEGER;
    seconds INTEGER;
BEGIN
    IF total_seconds IS NULL THEN
        RETURN NULL;
    END IF;

    hours = total_seconds / 3600;
    minutes = (total_seconds % 3600) / 60;
    seconds = total_seconds % 60;

    RETURN LPAD(hours::TEXT, 2, '0') || ':' ||
           LPAD(minutes::TEXT, 2, '0') || ':' ||
           LPAD(seconds::TEXT, 2, '0');
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

## 4. 시드 데이터 (Seed Data)

### 4.1 프로젝트 초기 데이터

```sql
INSERT INTO projects (code, name, description, nas_base_path, is_active) VALUES
('WSOP', 'World Series of Poker', 'WSOP 공식 영상', '\\10.10.100.122\docker\GGPNAs\ARCHIVE\WSOP', true),
('HCL', 'Hustler Casino Live', '허슬러 카지노 라이브', '\\10.10.100.122\docker\GGPNAs\ARCHIVE\HCL', false),
('GGMILLIONS', 'GGMillions Super High Roller', 'GGMillions 슈퍼 하이롤러', '\\10.10.100.122\docker\GGPNAs\ARCHIVE\GGMillions', true),
('MPP', 'Mediterranean Poker Party', 'MPP 토너먼트', '\\10.10.100.122\docker\GGPNAs\ARCHIVE\MPP', true),
('PAD', 'Poker After Dark', 'Poker After Dark TV 시리즈', '\\10.10.100.122\docker\GGPNAs\ARCHIVE\PAD', true),
('GOG', 'GOG Series', 'GOG 시리즈', '\\10.10.100.122\docker\GGPNAs\ARCHIVE\GOG 최종', true),
('OTHER', 'Other', '기타 콘텐츠', NULL, true);
```

### 4.2 태그 초기 데이터

```sql
-- Poker Play Tags (9개)
INSERT INTO tags (category, name, name_display, sort_order) VALUES
('poker_play', 'preflop_allin', 'Preflop All-in', 1),
('poker_play', 'cooler', 'Cooler', 2),
('poker_play', 'bad_beat', 'Bad Beat', 3),
('poker_play', 'bluff', 'Bluff', 4),
('poker_play', 'hero_call', 'Hero Call', 5),
('poker_play', 'hero_fold', 'Hero Fold', 6),
('poker_play', 'suckout', 'Suckout', 7),
('poker_play', 'slow_play', 'Slow Play', 8),
('poker_play', 'value_bet', 'Value Bet', 9);

-- Emotion Tags (6개)
INSERT INTO tags (category, name, name_display, sort_order) VALUES
('emotion', 'stressed', 'Stressed', 1),
('emotion', 'excitement', 'Excitement', 2),
('emotion', 'relief', 'Relief', 3),
('emotion', 'intense', 'Intense', 4),
('emotion', 'shocked', 'Shocked', 5),
('emotion', 'disappointed', 'Disappointed', 6);

-- Epic Hand Tags (4개)
INSERT INTO tags (category, name, name_display, sort_order) VALUES
('epic_hand', 'royal_flush', 'Royal Flush', 1),
('epic_hand', 'straight_flush', 'Straight Flush', 2),
('epic_hand', 'quads', 'Quads', 3),
('epic_hand', 'full_house_over', 'Full House over Full House', 4);

-- Runout Tags (4개)
INSERT INTO tags (category, name, name_display, sort_order) VALUES
('runout', 'runner_runner', 'Runner Runner', 1),
('runout', 'one_out', '1 Out', 2),
('runout', 'dirty', 'Dirty', 3),
('runout', 'clean', 'Clean', 4);

-- Adjective Tags (5개)
INSERT INTO tags (category, name, name_display, sort_order) VALUES
('adjective', 'brutal', 'Brutal', 1),
('adjective', 'incredible', 'Incredible', 2),
('adjective', 'insane', 'Insane', 3),
('adjective', 'sick', 'Sick', 4),
('adjective', 'amazing', 'Amazing', 5);
```

### 4.3 Google Sheet Sync 초기 설정

```sql
INSERT INTO google_sheet_sync (sheet_id, sheet_name, entity_type, sync_status) VALUES
('1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4', 'hand_analysis', 'hand_clip', 'pending'),
('1pUMPKe-OsKc-Xd8lH1cP9ctJO4hj3keXY5RwNFp2Mtk', 'hand_database', 'hand_clip', 'pending');
```

---

## 5. 인덱스 전략

### 5.1 검색 최적화 인덱스

```sql
-- Full-Text Search 인덱스 (제목, 설명)
CREATE INDEX idx_hand_clips_title_fts ON hand_clips
    USING gin(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(description, '')));

CREATE INDEX idx_players_name_fts ON players
    USING gin(to_tsvector('english', name || ' ' || COALESCE(name_display, '')));

-- 복합 인덱스 (자주 사용되는 쿼리 패턴)
CREATE INDEX idx_hand_clips_search ON hand_clips(hand_grade, video_file_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_events_search ON events(season_id, event_type, game_type)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_video_files_search ON video_files(episode_id, version_type, file_format)
    WHERE deleted_at IS NULL;
```

### 5.2 외래키 인덱스

```sql
-- 모든 FK 컬럼에 인덱스 생성 (이미 위에서 생성됨)
-- 목록 확인용
SELECT
    t.relname AS table_name,
    i.relname AS index_name,
    a.attname AS column_name
FROM
    pg_class t,
    pg_class i,
    pg_index ix,
    pg_attribute a
WHERE
    t.oid = ix.indrelid
    AND i.oid = ix.indexrelid
    AND a.attrelid = t.oid
    AND a.attnum = ANY(ix.indkey)
    AND t.relkind = 'r'
    AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'pokervod')
ORDER BY
    t.relname,
    i.relname;
```

---

## 6. Views (뷰)

### 6.1 핸드 클립 상세 뷰

```sql
CREATE OR REPLACE VIEW v_hand_clip_details AS
SELECT
    hc.id,
    hc.title,
    hc.timecode_in,
    hc.timecode_out,
    hc.hand_grade,
    hc.winner_hand,
    hc.hands_involved,
    hc.description,
    vf.file_path,
    vf.file_name,
    e.title AS episode_title,
    ev.name AS event_name,
    ev.event_type,
    ev.game_type,
    s.year,
    s.location,
    p.name AS project_name,
    p.code AS project_code,
    array_agg(DISTINCT t.name_display) FILTER (WHERE t.category = 'poker_play') AS poker_play_tags,
    array_agg(DISTINCT t.name_display) FILTER (WHERE t.category = 'emotion') AS emotion_tags,
    array_agg(DISTINCT pl.name) AS players
FROM hand_clips hc
LEFT JOIN video_files vf ON hc.video_file_id = vf.id
LEFT JOIN episodes e ON hc.episode_id = e.id
LEFT JOIN events ev ON e.event_id = ev.id
LEFT JOIN seasons s ON ev.season_id = s.id
LEFT JOIN projects p ON s.project_id = p.id
LEFT JOIN hand_clip_tags hct ON hc.id = hct.hand_clip_id
LEFT JOIN tags t ON hct.tag_id = t.id
LEFT JOIN hand_clip_players hcp ON hc.id = hcp.hand_clip_id
LEFT JOIN players pl ON hcp.player_id = pl.id
WHERE hc.deleted_at IS NULL
GROUP BY
    hc.id, vf.id, e.id, ev.id, s.id, p.id;

COMMENT ON VIEW v_hand_clip_details IS '핸드 클립 상세 정보 (조인된 뷰)';
```

### 6.2 동기화 상태 뷰

```sql
CREATE OR REPLACE VIEW v_sync_status AS
SELECT
    'nas_scan' AS sync_type,
    project_code AS source,
    scan_status AS status,
    last_scanned_at AS last_sync,
    total_files AS total_count,
    new_files_count AS new_count,
    error_message
FROM nas_scan_checkpoints
UNION ALL
SELECT
    'sheet_sync' AS sync_type,
    sheet_name AS source,
    sync_status AS status,
    last_synced_at AS last_sync,
    row_count AS total_count,
    new_rows_count AS new_count,
    error_message
FROM google_sheet_sync;

COMMENT ON VIEW v_sync_status IS '통합 동기화 상태';
```

---

## 7. 마이그레이션 전략

### 7.1 pokervod.db (SQLite) → PostgreSQL 마이그레이션

```sql
-- 1. 기존 테이블 매핑
-- catalogs → projects
-- series → seasons
-- contents → episodes
-- files → video_files
-- tags → tags (category 추가)
-- players → players

-- 2. 마이그레이션 스크립트 예시
-- (별도 Python 스크립트로 실행)
```

### 7.2 버전 관리

```sql
-- 스키마 버전 테이블
CREATE TABLE schema_versions (
    version VARCHAR(20) PRIMARY KEY,
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_versions (version, description) VALUES
('1.0.0', 'Initial schema - 16 tables, core + sync');
```

---

## 8. 참조

| 문서 | 설명 |
|------|------|
| [LLD_INDEX.md](./LLD_INDEX.md) | LLD 인덱스 |
| [02_SYNC_SYSTEM.md](./02_SYNC_SYSTEM.md) | 동기화 시스템 상세 |
| [PRD.md](../PRD.md) | 제품 요구사항 문서 |

---

**문서 버전**: 1.0.0
**작성일**: 2025-12-09
**상태**: Initial Release
