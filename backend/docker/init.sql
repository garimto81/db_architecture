-- GGP Poker Video Catalog DB - Initial Schema
-- Version: 1.0.0
-- Generated from: docs/lld/01_DATABASE_SCHEMA.md

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Timezone
SET timezone = 'Asia/Seoul';

-- Schema
CREATE SCHEMA IF NOT EXISTS pokervod;
SET search_path TO pokervod, public;

-- ============================================
-- Core Tables (5 tables for Phase 1)
-- ============================================

-- 1. projects
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

-- 2. seasons
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

-- 3. events
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
        event_type IS NULL OR event_type IN (
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

-- 4. episodes
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

-- 5. video_files
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

-- ============================================
-- Seed Data (Initial Projects)
-- ============================================

INSERT INTO projects (code, name, description, is_active) VALUES
    ('WSOP', 'World Series of Poker', 'The most prestigious poker tournament series', true),
    ('HCL', 'Hustler Casino Live', 'High stakes cash game streaming', true),
    ('GGMILLIONS', 'GGMillions Super High Roller', 'GGPoker online super high roller series', true),
    ('MPP', 'Mystery Poker Pro', 'Mystery bounty tournament series', true),
    ('PAD', 'Poker After Dark', 'Classic poker TV series', true),
    ('GOG', 'Game of Gold', 'PokerGO original series', true),
    ('OTHER', 'Other Projects', 'Miscellaneous poker content', true);

-- Sample Season for WSOP
INSERT INTO seasons (project_id, year, name, location, sub_category, status)
SELECT id, 2024, '2024 WSOP Las Vegas', 'Las Vegas, NV', 'BRACELET_LV', 'completed'
FROM projects WHERE code = 'WSOP';

-- Sample Season for HCL
INSERT INTO seasons (project_id, year, name, location, status)
SELECT id, 2024, 'HCL Season 2024', 'Los Angeles, CA', 'active'
FROM projects WHERE code = 'HCL';

-- ============================================
-- Google Sheets Sync Tables
-- ============================================

-- 6. google_sheet_sync (동기화 상태 추적)
CREATE TABLE google_sheet_sync (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sheet_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    last_row_synced INTEGER DEFAULT 0,
    last_synced_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sheet_id, entity_type)
);

COMMENT ON TABLE google_sheet_sync IS 'Google Sheet 동기화 상태 추적';

-- 7. hand_clips (핸드 클립 메타데이터)
CREATE TABLE hand_clips (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    episode_id UUID REFERENCES episodes(id) ON DELETE SET NULL,
    video_file_id UUID REFERENCES video_files(id) ON DELETE SET NULL,
    sheet_source VARCHAR(50),
    sheet_row_number INTEGER,
    title VARCHAR(500),
    timecode VARCHAR(20),
    timecode_end VARCHAR(20),
    duration_seconds INTEGER,
    notes TEXT,
    hand_grade VARCHAR(10),
    pot_size INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sheet_source, sheet_row_number)
);

CREATE INDEX idx_hand_clips_episode ON hand_clips(episode_id);
CREATE INDEX idx_hand_clips_video ON hand_clips(video_file_id);
CREATE INDEX idx_hand_clips_source ON hand_clips(sheet_source);

COMMENT ON TABLE hand_clips IS '핸드 클립 메타데이터 (Google Sheets 연동)';

COMMENT ON SCHEMA pokervod IS 'GGP Poker Video Catalog Database v1.1.0';
