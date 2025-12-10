"""
Google Sheets Sync Service

Syncs hand clip data from Google Sheets to database.
Implements rate limiting and incremental sync based on row numbers.
"""
import os
import ntpath  # Windows 경로 처리용 (크로스 플랫폼)
import re
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)


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


class TitleNormalizer:
    """
    제목 정규화 유틸리티 (Issue #32: Hybrid Fuzzy Matching)

    iconik_metadata 제목을 video_files.file_name과 매칭하기 위해 정규화:
    - _subclip_ 이후 텍스트 제거
    - _PGM, ES코드, GMPO 코드 제거
    - 파일 확장자 제거
    - 언더스코어/하이픈 → 공백 변환
    - 소문자 변환
    """

    # 제거할 패턴 (순서 중요)
    REMOVE_PATTERNS = [
        r'_subclip_.*$',           # _subclip_ 이후 모든 텍스트
        r'_subclip$',              # _subclip만 있는 경우
        r'_PGM$',                  # _PGM 접미사
        r'[_\s]ES[O0]\d{9,10}',    # ES 코드 (ESO 또는 ES0 + 9-10자리)
        r'[_\s]GMPO\s*\d+',        # GMPO 코드
        r'\.(mp4|mov|mxf|avi|mkv)$',  # 파일 확장자
    ]

    # 컴파일된 패턴 캐시
    _compiled_patterns = None

    @classmethod
    def _get_patterns(cls):
        """컴파일된 패턴 반환 (캐싱)"""
        if cls._compiled_patterns is None:
            cls._compiled_patterns = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in cls.REMOVE_PATTERNS
            ]
        return cls._compiled_patterns

    @classmethod
    def normalize(cls, title: str) -> str:
        """
        제목 정규화

        Args:
            title: 원본 제목

        Returns:
            정규화된 제목 (소문자, 공백으로 구분)
        """
        if not title:
            return ""

        result = title.strip()

        # 패턴 제거
        for pattern in cls._get_patterns():
            result = pattern.sub('', result)

        # 언더스코어/하이픈 → 공백
        result = re.sub(r'[_\-]+', ' ', result)

        # 연속 공백 정리
        result = re.sub(r'\s+', ' ', result)

        # 소문자 변환 및 trim
        return result.lower().strip()


class NasPathNormalizer:
    """
    NAS 경로 정규화 유틸리티

    Issue #30: Google Sheets의 Nas Folder Link를 DB 경로 형식으로 변환
    - UNC 경로 (\\10.10.100.122\docker\GGPNAs\...) → Z:/GGPNAs/...
    - Docker 경로 (/nas/ARCHIVE/...) → Z:/GGPNAs/ARCHIVE/...
    - 백슬래시 → 포워드슬래시
    """

    # 경로 변환 매핑 (순서 중요: 더 구체적인 패턴이 먼저)
    PATH_MAPPINGS = [
        # UNC 경로 (이중 백슬래시 포함)
        (r'\\\\10\.10\.100\.122\\docker\\GGPNAs\\', 'Z:/GGPNAs/'),
        (r'//10\.10\.100\.122/docker/GGPNAs/', 'Z:/GGPNAs/'),
        # Docker 마운트 경로
        (r'/nas/', 'Z:/GGPNAs/'),
    ]

    @classmethod
    def normalize(cls, path: str) -> str:
        """
        경로를 DB 저장 형식(Z:\...)으로 정규화

        Args:
            path: 원본 경로 (UNC, Docker, Windows)

        Returns:
            정규화된 경로 (backslash, Z: 드라이브) - DB 형식과 일치
        """
        if not path:
            return ""

        # 먼저 포워드슬래시로 통일 (패턴 매칭용)
        normalized = path.replace('\\', '/')

        # 이중 슬래시 정리
        while '//' in normalized and not normalized.startswith('//10'):
            normalized = normalized.replace('//', '/')

        # 매핑 적용
        for pattern, replacement in cls.PATH_MAPPINGS:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        # DB 형식에 맞게 백슬래시로 변환 (Z:/... → Z:\...)
        normalized = normalized.replace('/', '\\')

        return normalized

    @classmethod
    def to_db_path(cls, sheet_path: str) -> str:
        """Sheet 경로 → DB 검색용 경로 (normalize의 별칭)"""
        return cls.normalize(sheet_path)


class VideoFileMatcher:
    """
    Nas Folder Link → video_files.file_path 매칭

    Issue #30: Google Sheets의 NAS 경로로 video_files.id를 찾음
    """

    def __init__(self, db: Session):
        self.db = db
        self.normalizer = NasPathNormalizer()

        # 캐시: file_path → video_file_id (메모리 효율)
        self._path_cache: Dict[str, UUID] = {}

    def find_video_file_id(self, nas_path: str) -> Optional[UUID]:
        """
        NAS 경로로 video_file_id 조회

        전략:
        1. 정확한 file_path 매칭 (가장 빠름)
        2. 확장자 추가해서 매칭 (.mp4, .mov 등)
        3. 파일명 LIKE 검색 (확장자 무시)
        """
        if not nas_path:
            return None

        normalized = self.normalizer.to_db_path(nas_path)

        # 1. 캐시 확인
        if normalized in self._path_cache:
            return self._path_cache[normalized]

        # 2. 정확한 매칭
        result = self.db.execute(
            text("""
                SELECT id FROM pokervod.video_files
                WHERE file_path = :path
                LIMIT 1
            """),
            {'path': normalized}
        ).first()

        if result:
            self._path_cache[normalized] = result[0]
            return result[0]

        # 3. 확장자가 없는 경우 일반적인 비디오 확장자 추가해서 시도
        # ntpath.basename() 사용: Linux에서도 Windows 경로 처리 가능
        filename = ntpath.basename(normalized)
        if filename and not any(filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv']):
            for ext in ['.mp4', '.mov', '.avi', '.mkv']:
                result = self.db.execute(
                    text("""
                        SELECT id FROM pokervod.video_files
                        WHERE file_name = :filename
                        LIMIT 1
                    """),
                    {'filename': filename + ext}
                ).first()

                if result:
                    self._path_cache[normalized] = result[0]
                    return result[0]

        # 4. 파일명 LIKE 검색 (확장자 무시, 폴더 경로 변경 대응)
        if filename:
            # 확장자 제거한 이름으로 LIKE 검색
            name_without_ext = ntpath.splitext(filename)[0]
            if name_without_ext:
                result = self.db.execute(
                    text("""
                        SELECT id FROM pokervod.video_files
                        WHERE file_name LIKE :pattern
                        LIMIT 1
                    """),
                    {'pattern': name_without_ext + '%'}
                ).first()

                if result:
                    self._path_cache[normalized] = result[0]
                    return result[0]

        return None

    def preload_cache(self):
        """video_files 전체를 캐시에 로드 (대량 동기화 시)"""
        results = self.db.execute(
            text("""
                SELECT id, file_path, file_name
                FROM pokervod.video_files
                WHERE deleted_at IS NULL
            """)
        ).fetchall()

        for row in results:
            self._path_cache[row[1]] = row[0]  # file_path → id


class FuzzyMatcher:
    """
    Fuzzy 매칭으로 video_file_id 찾기 (Issue #32)

    NAS 경로가 없는 iconik_metadata 레코드에서
    제목(title) 기반으로 video_files와 매칭

    전략:
    1. pg_trgm similarity() 함수로 후보군 필터링 (DB 레벨)
    2. TitleNormalizer로 제목 정규화
    3. 신뢰도 점수 기반 자동/수동 분류
    """

    # 매칭 임계값
    AUTO_MATCH_THRESHOLD = 70    # 자동 매칭 (70% 이상)
    REVIEW_THRESHOLD = 50        # 수동 검토 (50-70%)
    MIN_SIMILARITY = 0.3         # pg_trgm 최소 유사도

    def __init__(self, db: Session):
        self.db = db
        self._candidates_cache: Dict[str, List[Tuple]] = {}

    def find_best_match(self, clip_title: str) -> Optional[Dict]:
        """
        제목으로 최적의 video_file 매칭 찾기

        Args:
            clip_title: hand_clips.title

        Returns:
            {
                'video_file_id': UUID,
                'file_name': str,
                'confidence': int (0-100),
                'method': 'fuzzy',
                'needs_review': bool
            }
            또는 매칭 없으면 None
        """
        if not clip_title:
            return None

        # 1. pg_trgm으로 후보군 검색
        candidates = self._get_candidates(clip_title)

        if not candidates:
            return None

        # 2. 정규화된 제목으로 최적 매칭 선택
        normalized_title = TitleNormalizer.normalize(clip_title)

        best_match = None
        best_score = 0

        for video_id, file_name, pg_similarity in candidates:
            # pg_trgm 유사도를 100점 만점으로 변환
            confidence = int(pg_similarity * 100)

            # 정규화된 파일명과 추가 비교 (선택적)
            normalized_filename = TitleNormalizer.normalize(file_name)

            if confidence > best_score:
                best_score = confidence
                best_match = {
                    'video_file_id': video_id,
                    'file_name': file_name,
                    'confidence': confidence,
                    'method': 'fuzzy',
                    'needs_review': confidence < self.AUTO_MATCH_THRESHOLD
                }

        return best_match

    def _get_candidates(self, clip_title: str, limit: int = 10) -> List[Tuple]:
        """
        pg_trgm으로 유사한 video_files 후보 검색

        Args:
            clip_title: 검색할 제목
            limit: 최대 후보 수

        Returns:
            [(video_id, file_name, similarity), ...]
        """
        # 캐시 확인
        cache_key = clip_title[:50]  # 긴 제목은 앞 50자만
        if cache_key in self._candidates_cache:
            return self._candidates_cache[cache_key]

        try:
            result = self.db.execute(
                text("""
                    SELECT id, file_name, similarity(file_name, :title) as score
                    FROM pokervod.video_files
                    WHERE similarity(file_name, :title) > :min_sim
                      AND deleted_at IS NULL
                    ORDER BY score DESC
                    LIMIT :limit
                """),
                {
                    'title': clip_title,
                    'min_sim': self.MIN_SIMILARITY,
                    'limit': limit
                }
            ).fetchall()

            candidates = [(row[0], row[1], row[2]) for row in result]
            self._candidates_cache[cache_key] = candidates
            return candidates

        except Exception as e:
            logger.error(f"FuzzyMatcher query failed: {e}")
            return []

    def batch_match(self, clips: List[Dict]) -> List[Dict]:
        """
        여러 클립 일괄 매칭

        Args:
            clips: [{'id': UUID, 'title': str}, ...]

        Returns:
            [{'clip_id': UUID, 'matched': bool, 'result': Dict or None}, ...]
        """
        results = []

        for clip in clips:
            match_result = self.find_best_match(clip.get('title', ''))

            results.append({
                'clip_id': clip.get('id'),
                'matched': match_result is not None,
                'result': match_result
            })

        return results

    def get_statistics(self) -> Dict:
        """매칭 통계 조회"""
        stats = self.db.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(video_file_id) as matched,
                    COUNT(*) - COUNT(video_file_id) as unmatched
                FROM pokervod.hand_clips
                WHERE sheet_source = 'iconik_metadata'
            """)
        ).first()

        return {
            'total': stats[0] if stats else 0,
            'matched': stats[1] if stats else 0,
            'unmatched': stats[2] if stats else 0,
            'match_rate': round(stats[1] / stats[0] * 100, 1) if stats and stats[0] > 0 else 0
        }


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

        # Issue #30: video_file_id 매칭용
        self.video_matcher = VideoFileMatcher(db)

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

        # Issue #30: Nas Folder Link (C열) → video_file_id 매칭
        nas_path = get_col('nas_path')
        video_file_id = None
        if nas_path:
            video_file_id = self.video_matcher.find_video_file_id(nas_path)

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
            'video_file_id': video_file_id,            # Issue #30: 핵심 연결
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
            # Update existing (Issue #30: video_file_id 추가)
            self.db.execute(
                text("""
                    UPDATE pokervod.hand_clips
                    SET title = :title,
                        timecode = :timecode,
                        timecode_end = :timecode_end,
                        notes = :notes,
                        hand_grade = :hand_grade,
                        video_file_id = :video_file_id,
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
                    'video_file_id': str(clip_data.get('video_file_id')) if clip_data.get('video_file_id') else None,
                }
            )
            return False
        else:
            # Insert new (Issue #30: video_file_id 추가)
            self.db.execute(
                text("""
                    INSERT INTO pokervod.hand_clips (
                        id, sheet_source, sheet_row_number, title, timecode, timecode_end, notes, hand_grade, video_file_id
                    ) VALUES (
                        :id, :source, :row_num, :title, :timecode, :timecode_end, :notes, :hand_grade, :video_file_id
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
                    'video_file_id': str(clip_data.get('video_file_id')) if clip_data.get('video_file_id') else None,
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
