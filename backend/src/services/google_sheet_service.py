"""
Google Sheets Sync Service

Syncs hand clip data from Google Sheets to database.
Implements rate limiting and incremental sync based on row numbers.
"""
import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert


@dataclass
class SheetConfig:
    """Configuration for a Google Sheet"""
    sheet_id: str
    sheet_name: str
    source_type: str  # 'hand_analysis' or 'hand_database'
    column_mapping: Dict[str, int]  # column name -> column index (0-based)


@dataclass
class SyncState:
    """Sync state for a sheet"""
    sheet_id: str
    last_row_synced: int = 0
    last_synced_at: Optional[datetime] = None


@dataclass
class SheetSyncResult:
    """Result of a sheet sync operation"""
    sheet_id: str
    processed_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)
    status: str = "success"


class TagNormalizer:
    """
    Normalize tags from various formats to canonical form.
    Based on LLD 02 Section 4.2.
    """

    # Tag normalization rules
    NORMALIZATIONS = {
        # Poker plays
        r'preflop[\s_-]?all[\s_-]?in': 'preflop_allin',
        r'bad[\s_-]?beat': 'bad_beat',
        r'bluff[\s_-]?catch': 'bluff_catch',
        r'slow[\s_-]?play': 'slow_play',
        r'value[\s_-]?bet': 'value_bet',
        r'check[\s_-]?raise': 'check_raise',
        r'3[\s_-]?bet': 'three_bet',
        r'4[\s_-]?bet': 'four_bet',
        r'river[\s_-]?bluff': 'river_bluff',
        r'hero[\s_-]?call': 'hero_call',
        r'fold[\s_-]?to[\s_-]?bluff': 'fold_to_bluff',
        r'cooler': 'cooler',

        # Situations
        r'heads[\s_-]?up': 'heads_up',
        r'multi[\s_-]?way': 'multiway',
        r'short[\s_-]?stack': 'short_stack',
        r'deep[\s_-]?stack': 'deep_stack',
        r'bubble': 'bubble',
        r'final[\s_-]?table': 'final_table',

        # Hand strengths
        r'royal[\s_-]?flush': 'royal_flush',
        r'straight[\s_-]?flush': 'straight_flush',
        r'quads': 'quads',
        r'full[\s_-]?house': 'full_house',
        r'flush': 'flush',
        r'straight': 'straight',
        r'set': 'set',
        r'trips': 'trips',
        r'two[\s_-]?pair': 'two_pair',
        r'overpair': 'overpair',
        r'top[\s_-]?pair': 'top_pair',
    }

    # Compiled patterns for efficiency
    _compiled_patterns = None

    @classmethod
    def _get_patterns(cls):
        if cls._compiled_patterns is None:
            cls._compiled_patterns = [
                (re.compile(pattern, re.IGNORECASE), normalized)
                for pattern, normalized in cls.NORMALIZATIONS.items()
            ]
        return cls._compiled_patterns

    @classmethod
    def normalize(cls, tag: str) -> str:
        """Normalize a tag to canonical form"""
        if not tag:
            return ""

        tag = tag.strip()

        # Preserve star ratings
        if all(c == '★' or c == '☆' for c in tag):
            return tag

        # Try pattern matching
        for pattern, normalized in cls._get_patterns():
            if pattern.search(tag):
                return normalized

        # Default: lowercase and replace spaces/hyphens with underscore
        return re.sub(r'[\s-]+', '_', tag.lower())

    @classmethod
    def normalize_list(cls, tags_str: str, delimiter: str = ',') -> List[str]:
        """Normalize a comma-separated list of tags"""
        if not tags_str:
            return []

        tags = [t.strip() for t in tags_str.split(delimiter) if t.strip()]
        return [cls.normalize(t) for t in tags]


class GoogleSheetService:
    """
    Google Sheets synchronization service.
    Syncs hand clip data from configured sheets to database.
    """

    # Rate limiting settings
    MAX_REQUESTS_PER_MINUTE = 60
    BATCH_SIZE = 100

    # Default column mapping for Metadata Archive sheet (Issue #28: 실제 시트 구조 반영)
    # A: File No., B: File Name, C: Nas Folder Link, D: In, E: Out, F: Hand Grade,
    # G: Winner, H: Hands, I-K: Tag (Player) 1-3, L-R: Tag (Poker Play) 1-7, S-T: Tag (Emotion) 1-2
    HAND_ANALYSIS_COLUMNS = {
        'file_no': 0,           # A: File No. (클립 번호)
        'title': 1,             # B: File Name (제목)
        'nas_path': 2,          # C: Nas Folder Link
        'timecode': 3,          # D: In (시작 타임코드) ★ 핵심
        'timecode_end': 4,      # E: Out (종료 타임코드)
        'hand_grade': 5,        # F: Hand Grade (등급)
        'winner': 6,            # G: Winner (승자)
        'hands': 7,             # H: Hands (핸드 조합)
        'player_1': 8,          # I: Tag (Player) 1
        'player_2': 9,          # J: Tag (Player) 2
        'player_3': 10,         # K: Tag (Player) 3
        'tag_play_1': 11,       # L: Tag (Poker Play) 1
        'tag_play_2': 12,       # M: Tag (Poker Play) 2
        'tag_play_3': 13,       # N: Tag (Poker Play) 3
        'tag_play_4': 14,       # O: Tag (Poker Play) 4
        'tag_play_5': 15,       # P: Tag (Poker Play) 5
        'tag_play_6': 16,       # Q: Tag (Poker Play) 6
        'tag_play_7': 17,       # R: Tag (Poker Play) 7
        'tag_emotion_1': 18,    # S: Tag (Emotion) 1
        'tag_emotion_2': 19,    # T: Tag (Emotion) 2
    }

    # Default column mapping for hand_database sheet
    HAND_DATABASE_COLUMNS = {
        'hand_id': 0,
        'video_title': 1,
        'timecode': 2,
        'players': 3,
        'action': 4,
        'pot_size': 5,
        'tags': 6,
        'notes': 7,
    }

    # Sheet configurations - 실제 시트 ID (PRD 기준)
    # Issue #28: 시트 이름 변경 및 iconik Metadata 보류
    SHEET_CONFIGS = {
        # Metadata Archive (구 Hand Analysis) - 현재 사용
        'metadata_archive': SheetConfig(
            sheet_id='1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4',
            sheet_name='Metadata Archive',
            source_type='metadata_archive',
            column_mapping=HAND_ANALYSIS_COLUMNS,
        ),
        # iconik Metadata (구 Hand Database) - 사용 보류
        # 'iconik_metadata': SheetConfig(
        #     sheet_id='1pUMPKe-OsKc-Xd8lH1cP9ctJO4hj3keXY5RwNFp2Mtk',
        #     sheet_name='iconik Metadata',
        #     source_type='iconik_metadata',
        #     column_mapping=HAND_DATABASE_COLUMNS,
        # ),
    }

    # Legacy aliases for backward compatibility
    LEGACY_SHEET_ALIASES = {
        'hand_analysis': 'metadata_archive',
        'hand_database': 'iconik_metadata',  # 보류됨
    }

    def __init__(self, db: Session, credentials_path: Optional[str] = None):
        """
        Initialize the service.

        Args:
            db: SQLAlchemy session
            credentials_path: Path to Google API credentials JSON (or use GOOGLE_SHEETS_CREDENTIALS env var)
        """
        self.db = db
        # 환경변수에서 인증 파일 경로 가져오기 (우선순위: 파라미터 > 환경변수)
        self.credentials_path = credentials_path or os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        self._client = None
        self._request_count = 0
        self._request_window_start = time.time()

    def _get_client(self):
        """Get or create gspread client (lazy initialization)"""
        if self._client is None:
            try:
                import gspread
                from google.oauth2.service_account import Credentials

                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets.readonly',
                    'https://www.googleapis.com/auth/drive.readonly',
                ]

                if self.credentials_path:
                    creds = Credentials.from_service_account_file(
                        self.credentials_path, scopes=scopes
                    )
                    self._client = gspread.authorize(creds)
                else:
                    # Use default credentials (for testing without actual API)
                    self._client = None
            except ImportError:
                # gspread not installed
                self._client = None

        return self._client

    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()

        # Reset window if needed
        if current_time - self._request_window_start > 60:
            self._request_count = 0
            self._request_window_start = current_time

        self._request_count += 1

        # Sleep if over limit
        if self._request_count > self.MAX_REQUESTS_PER_MINUTE:
            sleep_time = min(2 ** (self._request_count - self.MAX_REQUESTS_PER_MINUTE), 60)
            time.sleep(sleep_time)

    def get_sync_state(self, sheet_id: str) -> SyncState:
        """Get sync state for a sheet from database"""
        # Query google_sheet_sync table
        result = self.db.execute(
            text("""
                SELECT last_row_synced, last_synced_at
                FROM pokervod.google_sheet_sync
                WHERE sheet_id = :sheet_id
            """),
            {'sheet_id': sheet_id}
        ).first()

        if result:
            return SyncState(
                sheet_id=sheet_id,
                last_row_synced=result[0] or 0,
                last_synced_at=result[1],
            )

        return SyncState(sheet_id=sheet_id)

    def update_sync_state(self, sheet_id: str, last_row: int):
        """Update sync state in database"""
        self.db.execute(
            text("""
                INSERT INTO pokervod.google_sheet_sync (sheet_id, entity_type, last_row_synced, last_synced_at)
                VALUES (:sheet_id, 'hand_clip', :last_row, NOW())
                ON CONFLICT (sheet_id, entity_type)
                DO UPDATE SET last_row_synced = :last_row, last_synced_at = NOW()
            """),
            {'sheet_id': sheet_id, 'last_row': last_row}
        )
        self.db.commit()

    def sync_sheet(
        self,
        sheet_key: str,
        limit: Optional[int] = None,
    ) -> SheetSyncResult:
        """
        Sync a single sheet to database.

        Args:
            sheet_key: Key in SHEET_CONFIGS ('hand_analysis' or 'hand_database')
            limit: Max rows to process (for testing)

        Returns:
            SheetSyncResult with counts and status
        """
        config = self.SHEET_CONFIGS.get(sheet_key)
        if not config:
            return SheetSyncResult(
                sheet_id=sheet_key,
                status='error',
                errors=[f"Unknown sheet key: {sheet_key}"],
            )

        result = SheetSyncResult(sheet_id=config.sheet_id)

        # Get client
        client = self._get_client()
        if not client:
            result.status = 'skipped'
            result.errors.append("Google Sheets client not available (gspread not installed or no credentials)")
            return result

        try:
            # Get sync state
            sync_state = self.get_sync_state(config.sheet_id)
            start_row = sync_state.last_row_synced + 1

            # Open worksheet
            self._rate_limit()
            spreadsheet = client.open_by_key(config.sheet_id)
            worksheet = spreadsheet.sheet1

            # Get total rows
            self._rate_limit()
            total_rows = worksheet.row_count

            if limit:
                total_rows = min(total_rows, start_row + limit)

            # Process in batches
            for batch_start in range(start_row, total_rows + 1, self.BATCH_SIZE):
                batch_end = min(batch_start + self.BATCH_SIZE - 1, total_rows)

                self._rate_limit()
                rows = worksheet.get(f'A{batch_start}:Z{batch_end}')

                if not rows:
                    break

                new, updated, errors = self._process_batch(
                    rows, batch_start, config
                )
                result.new_count += new
                result.updated_count += updated
                result.error_count += len(errors)
                result.errors.extend(errors[:5])  # Limit errors

                result.processed_count += len(rows)

                # Brief pause between batches
                time.sleep(1)

            # Update sync state
            self.update_sync_state(
                config.sheet_id,
                sync_state.last_row_synced + result.processed_count
            )

        except Exception as e:
            result.status = 'error'
            result.errors.append(str(e))

        return result

    def _process_batch(
        self,
        rows: List[List[str]],
        start_row: int,
        config: SheetConfig,
    ) -> Tuple[int, int, List[str]]:
        """Process a batch of rows"""
        new_count = 0
        updated_count = 0
        errors = []

        for idx, row in enumerate(rows):
            row_num = start_row + idx

            try:
                if not row or not row[0]:  # Skip empty rows
                    continue

                clip_data = self._parse_row(row, row_num, config)

                if clip_data:
                    is_new = self._upsert_hand_clip(clip_data)
                    if is_new:
                        new_count += 1
                    else:
                        updated_count += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        self.db.commit()
        return new_count, updated_count, errors

    def _parse_row(
        self,
        row: List[str],
        row_num: int,
        config: SheetConfig,
    ) -> Optional[Dict[str, Any]]:
        """Parse a row into hand clip data (Issue #28: 실제 시트 구조 반영)"""
        mapping = config.column_mapping

        def get_col(name: str) -> Optional[str]:
            idx = mapping.get(name)
            if idx is not None and idx < len(row):
                return row[idx].strip() if row[idx] else None
            return None

        # Issue #28: Metadata Archive 시트 구조에 맞게 매핑
        clip_data = {
            'id': uuid4(),
            'sheet_source': config.source_type,
            'sheet_row_number': row_num,
            'title': get_col('title') or get_col('video_title'),
            'timecode': get_col('timecode'),           # D열: In (시작 타임코드)
            'timecode_end': get_col('timecode_end'),   # E열: Out (종료 타임코드)
            'hand_grade': get_col('hand_grade'),       # F열: Hand Grade
            'notes': get_col('winner'),                # G열: Winner → notes에 임시 저장
        }

        # Parse hands involved (H열)
        hands_str = get_col('hands')
        if hands_str:
            clip_data['hands_involved'] = hands_str

        # Parse players (I-K열: Tag (Player) 1-3)
        players = []
        for i in range(1, 4):
            player = get_col(f'player_{i}')
            if player:
                players.append(player)
        if players:
            clip_data['players'] = players

        # Parse poker play tags (L-R열: Tag (Poker Play) 1-7)
        play_tags = []
        for i in range(1, 8):
            tag = get_col(f'tag_play_{i}')
            if tag:
                play_tags.append(TagNormalizer.normalize(tag))
        if play_tags:
            clip_data['normalized_tags'] = play_tags

        # Parse emotion tags (S-T열: Tag (Emotion) 1-2)
        emotion_tags = []
        for i in range(1, 3):
            tag = get_col(f'tag_emotion_{i}')
            if tag:
                emotion_tags.append(TagNormalizer.normalize(tag))
        if emotion_tags:
            clip_data['emotion_tags'] = emotion_tags

        # Legacy: Parse pot size if available (hand_database용)
        pot_str = get_col('pot_size')
        if pot_str:
            try:
                pot_clean = re.sub(r'[^\d.]', '', pot_str)
                clip_data['pot_size'] = int(float(pot_clean))
            except ValueError:
                pass

        return clip_data

    def _upsert_hand_clip(self, clip_data: Dict[str, Any]) -> bool:
        """
        Insert or update hand clip. Returns True if new.

        Note: This is a simplified implementation. In production,
        use the actual hand_clips table from LLD 01.
        """
        # Check if exists by sheet_source + sheet_row_number
        existing = self.db.execute(
            text("""
                SELECT id FROM pokervod.hand_clips
                WHERE sheet_source = :source AND sheet_row_number = :row_num
            """),
            {
                'source': clip_data['sheet_source'],
                'row_num': clip_data['sheet_row_number'],
            }
        ).first()

        if existing:
            # Update existing (Issue #28: timecode_end 추가)
            self.db.execute(
                text("""
                    UPDATE pokervod.hand_clips
                    SET title = :title,
                        timecode = :timecode,
                        timecode_end = :timecode_end,
                        notes = :notes,
                        hand_grade = :hand_grade,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    'id': existing[0],
                    'title': clip_data.get('title'),
                    'timecode': clip_data.get('timecode'),
                    'timecode_end': clip_data.get('timecode_end'),
                    'notes': clip_data.get('notes'),
                    'hand_grade': clip_data.get('hand_grade'),
                }
            )
            return False
        else:
            # Insert new (Issue #28: timecode_end 추가)
            self.db.execute(
                text("""
                    INSERT INTO pokervod.hand_clips (
                        id, sheet_source, sheet_row_number, title, timecode, timecode_end, notes, hand_grade, is_active
                    ) VALUES (
                        :id, :source, :row_num, :title, :timecode, :timecode_end, :notes, :hand_grade, true
                    )
                """),
                {
                    'id': str(clip_data['id']),
                    'source': clip_data['sheet_source'],
                    'row_num': clip_data['sheet_row_number'],
                    'title': clip_data.get('title'),
                    'timecode': clip_data.get('timecode'),
                    'timecode_end': clip_data.get('timecode_end'),
                    'notes': clip_data.get('notes'),
                    'hand_grade': clip_data.get('hand_grade'),
                }
            )
            return True

    def sync_all(self) -> Dict[str, SheetSyncResult]:
        """Sync all configured sheets"""
        results = {}

        for sheet_key in self.SHEET_CONFIGS:
            results[sheet_key] = self.sync_sheet(sheet_key)

        return results

    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status for all configured sheets"""
        status = {}

        for sheet_key, config in self.SHEET_CONFIGS.items():
            sync_state = self.get_sync_state(config.sheet_id)

            status[sheet_key] = {
                'sheet_id': config.sheet_id,
                'sheet_name': config.sheet_name,
                'source_type': config.source_type,
                'last_row_synced': sync_state.last_row_synced,
                'last_synced_at': sync_state.last_synced_at.isoformat() if sync_state.last_synced_at else None,
            }

        return status
