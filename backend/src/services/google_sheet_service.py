"""
Google Sheets Sync Service

Syncs hand clip data from Google Sheets to database.
Implements rate limiting and incremental sync based on row numbers.
"""
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

    # Default column mapping for hand_analysis sheet
    HAND_ANALYSIS_COLUMNS = {
        'timecode': 0,
        'title': 1,
        'players': 2,
        'tags': 3,
        'notes': 4,
        'hand_grade': 5,
        'video_ref': 6,
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

    # Sheet configurations
    SHEET_CONFIGS = {
        'hand_analysis': SheetConfig(
            sheet_id='1ABC...XYZ',  # Replace with actual sheet ID
            sheet_name='Hand Analysis',
            source_type='hand_analysis',
            column_mapping=HAND_ANALYSIS_COLUMNS,
        ),
        'hand_database': SheetConfig(
            sheet_id='1DEF...UVW',  # Replace with actual sheet ID
            sheet_name='Hand Database',
            source_type='hand_database',
            column_mapping=HAND_DATABASE_COLUMNS,
        ),
    }

    def __init__(self, db: Session, credentials_path: Optional[str] = None):
        """
        Initialize the service.

        Args:
            db: SQLAlchemy session
            credentials_path: Path to Google API credentials JSON
        """
        self.db = db
        self.credentials_path = credentials_path
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
        """Parse a row into hand clip data"""
        mapping = config.column_mapping

        def get_col(name: str) -> Optional[str]:
            idx = mapping.get(name)
            if idx is not None and idx < len(row):
                return row[idx].strip() if row[idx] else None
            return None

        clip_data = {
            'id': uuid4(),
            'sheet_source': config.source_type,
            'sheet_row_number': row_num,
            'timecode': get_col('timecode'),
            'title': get_col('title') or get_col('video_title'),
            'notes': get_col('notes'),
            'hand_grade': get_col('hand_grade'),
        }

        # Parse tags
        tags_str = get_col('tags')
        if tags_str:
            clip_data['normalized_tags'] = TagNormalizer.normalize_list(tags_str)

        # Parse players (comma-separated)
        players_str = get_col('players')
        if players_str:
            clip_data['players'] = [p.strip() for p in players_str.split(',') if p.strip()]

        # Parse pot size if available
        pot_str = get_col('pot_size')
        if pot_str:
            try:
                # Remove currency symbols and parse
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
            # Update existing
            self.db.execute(
                text("""
                    UPDATE pokervod.hand_clips
                    SET title = :title,
                        timecode = :timecode,
                        notes = :notes,
                        hand_grade = :hand_grade,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    'id': existing[0],
                    'title': clip_data.get('title'),
                    'timecode': clip_data.get('timecode'),
                    'notes': clip_data.get('notes'),
                    'hand_grade': clip_data.get('hand_grade'),
                }
            )
            return False
        else:
            # Insert new
            self.db.execute(
                text("""
                    INSERT INTO pokervod.hand_clips (
                        id, sheet_source, sheet_row_number, title, timecode, notes, hand_grade
                    ) VALUES (
                        :id, :source, :row_num, :title, :timecode, :notes, :hand_grade
                    )
                """),
                {
                    'id': str(clip_data['id']),
                    'source': clip_data['sheet_source'],
                    'row_num': clip_data['sheet_row_number'],
                    'title': clip_data.get('title'),
                    'timecode': clip_data.get('timecode'),
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
