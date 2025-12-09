"""
NAS Sync Service

Scans NAS directories and syncs video files to database.
Connects SyncAgent → ParserAgent → Database.
"""
import os
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from src.models import Project, Season, Event, Episode, VideoFile
from src.services.title_generator import get_title_generator
from src.services.catalog_title_generator import get_catalog_title_generator


@dataclass
class ParsedFile:
    """Parsed file metadata"""
    file_path: str
    file_name: str
    file_size: int
    modified_time: datetime
    project_code: str

    # Extracted metadata
    year: Optional[int] = None
    event_number: Optional[int] = None
    episode_number: Optional[int] = None
    day_number: Optional[int] = None
    part_number: Optional[int] = None
    title: Optional[str] = None
    event_type: Optional[str] = None
    game_type: Optional[str] = None
    table_type: Optional[str] = None
    version_type: Optional[str] = None
    buy_in: Optional[int] = None

    # Event grouping key (folder-based when event_number is not available)
    event_key: Optional[str] = None

    # Media info (optional, from ffprobe)
    duration_seconds: Optional[int] = None
    resolution: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    bitrate_kbps: Optional[int] = None


@dataclass
class ScanResult:
    """Scan operation result"""
    project_code: str
    scanned_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)
    status: str = "success"


@dataclass
class FilterResult:
    """File filter result"""
    file_path: str
    is_hidden: bool = False
    hidden_reason: Optional[str] = None


class FileFilter:
    """
    Filter files before processing.
    Marks files as hidden based on extension, patterns, and duplicates.
    """

    # Allowed extensions (mp4 only by default)
    ALLOWED_EXTENSIONS = {'.mp4'}

    # Patterns to exclude (macOS metadata files)
    EXCLUDE_PATTERNS = [
        re.compile(r'^\._'),           # macOS resource fork
        re.compile(r'^\.DS_Store$'),   # macOS folder metadata
        re.compile(r'^Thumbs\.db$'),   # Windows thumbnail cache
    ]

    def __init__(self, allowed_extensions: Optional[set] = None):
        if allowed_extensions:
            self.ALLOWED_EXTENSIONS = allowed_extensions

    def check_file(self, file_path: str) -> FilterResult:
        """Check if file should be hidden"""
        filename = Path(file_path).name
        ext = Path(file_path).suffix.lower()

        # Check macOS metadata files
        for pattern in self.EXCLUDE_PATTERNS:
            if pattern.match(filename):
                return FilterResult(file_path, True, 'macos_meta')

        # Check extension
        if ext not in self.ALLOWED_EXTENSIONS:
            return FilterResult(file_path, True, 'non_mp4')

        return FilterResult(file_path, False, None)

    def should_include(self, file_path: str) -> bool:
        """Quick check if file should be included in sync"""
        result = self.check_file(file_path)
        return not result.is_hidden


class FileParser:
    """
    Parse filenames to extract metadata.
    Project-specific patterns based on LLD 03_FILE_PARSER.md
    """

    # Video file extensions
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.mxf'}

    # WSOP Bracelet pattern
    # Example: 10-wsop-2024-be-ev-21-25k-nlh-hr-ft-title.mp4
    WSOP_BRACELET_PATTERN = re.compile(
        r'^(\d+)-wsop-(\d{4})-be-ev-(\d+)-'
        r'(\d+k?)-([a-z0-9]+)-?([a-z_]*)?-?([a-z0-9]*)?'
        r'(?:-(.+?))?\.(\w+)$',
        re.IGNORECASE
    )

    # WSOP Circuit pattern
    # Example: WCLA24-15.mp4
    WSOP_CIRCUIT_PATTERN = re.compile(
        r'^W([A-Z]{2,4})(\d{2})-(\d+)\.(\w+)$',
        re.IGNORECASE
    )

    # GGMillions pattern
    # Example: 250507_Super High Roller...with Joey Ingram.mp4
    GGMILLIONS_PATTERN = re.compile(
        r'^(\d{6})_(.+?)\.(\w+)$',
        re.IGNORECASE
    )

    # GOG pattern
    # Example: E01_GOG_final_edit_20231215.mp4
    GOG_PATTERN = re.compile(
        r'^E(\d+)_GOG_([a-z_]+)_(\d{8})\.(\w+)$',
        re.IGNORECASE
    )

    # PAD pattern
    # Example: PAD S12 E01.mp4
    PAD_PATTERN = re.compile(
        r'^PAD\s*S(\d+)\s*E(\d+)\.(\w+)$',
        re.IGNORECASE
    )

    # MPP pattern
    # Example: $1M GTD $1K Mystery Bounty.mp4
    MPP_PATTERN = re.compile(
        r'^\$?([\d.]+[MK]?)\s*GTD\s*\$?([\d.]+[MK]?)\s*(.+?)\.(\w+)$',
        re.IGNORECASE
    )

    # HCL pattern (generic for now)
    # Example: HCL_2024_01_15_session1.mp4
    HCL_PATTERN = re.compile(
        r'^HCL[_-]?(\d{4})[_-]?(\d{2})[_-]?(\d{2})[_-]?(.+?)\.(\w+)$',
        re.IGNORECASE
    )

    # Version type detection
    VERSION_PATTERNS = {
        'clean': re.compile(r'clean', re.IGNORECASE),
        'mastered': re.compile(r'master', re.IGNORECASE),
        'stream': re.compile(r'stream', re.IGNORECASE),
        'subclip': re.compile(r'subclip', re.IGNORECASE),
        'final_edit': re.compile(r'final[_-]?edit', re.IGNORECASE),
        'nobug': re.compile(r'nobug', re.IGNORECASE),
        'pgm': re.compile(r'\bpgm\b', re.IGNORECASE),
        'hires': re.compile(r'hires|hi[_-]?res', re.IGNORECASE),
    }

    # Game type mapping
    GAME_TYPES = {
        'nlh': 'NLHE', 'nlhe': 'NLHE', 'holdem': 'NLHE',
        'plo': 'PLO', 'omaha': 'PLO',
        'plo8': 'PLO8', 'nlo8': 'NLO8',
        'mixed': 'Mixed',
        'stud': 'Stud',
        'razz': 'Razz',
        'horse': 'HORSE',
        '27td': '2-7TD', '2-7td': '2-7TD',
        '27sd': '2-7SD', '2-7sd': '2-7SD',
        'badugi': 'Badugi',
        'oe': 'OE', '8game': 'Mixed',
    }

    # Valid game types from DB constraint
    VALID_GAME_TYPES = {'NLHE', 'PLO', 'PLO8', 'Mixed', 'Stud', 'Razz', 'HORSE', '2-7TD', '2-7SD', 'Badugi', 'OE', 'NLO8'}

    # Table type mapping (DB constraint: preliminary, day1, day2, day3, final_table, heads_up)
    TABLE_TYPES = {
        'ft': 'final_table',
        'final': 'final_table',
        'finaltable': 'final_table',
        'day1': 'day1', 'd1': 'day1', 'day01': 'day1',
        'day2': 'day2', 'd2': 'day2', 'day02': 'day2',
        'day3': 'day3', 'd3': 'day3', 'day03': 'day3',
        'preliminary': 'preliminary', 'prelim': 'preliminary',
        'headsup': 'heads_up', 'heads_up': 'heads_up', 'hu': 'heads_up',
    }

    # Valid table types from DB constraint
    VALID_TABLE_TYPES = {'preliminary', 'day1', 'day2', 'day3', 'final_table', 'heads_up'}

    def parse(self, file_path: str, project_code: str) -> ParsedFile:
        """Parse a file path and extract metadata"""
        path = Path(file_path)
        filename = path.name

        # Get file stats
        try:
            stat = path.stat()
            file_size = stat.st_size
            modified_time = datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            file_size = 0
            modified_time = datetime.now()

        parsed = ParsedFile(
            file_path=str(file_path),
            file_name=filename,
            file_size=file_size,
            modified_time=modified_time,
            project_code=project_code,
        )

        # Detect version type
        parsed.version_type = self._detect_version_type(filename)

        # Parse folder path first (more reliable for year/event grouping)
        self._parse_folder_path(parsed, str(file_path))

        # Parse based on project (may override folder-based parsing)
        if project_code == 'WSOP':
            self._parse_wsop(parsed, filename)
        elif project_code == 'GGMILLIONS':
            self._parse_ggmillions(parsed, filename)
        elif project_code == 'GOG':
            self._parse_gog(parsed, filename)
        elif project_code == 'PAD':
            self._parse_pad(parsed, filename)
        elif project_code == 'MPP':
            self._parse_mpp(parsed, filename)
        elif project_code == 'HCL':
            self._parse_hcl(parsed, filename)

        return parsed

    def _parse_folder_path(self, parsed: ParsedFile, file_path: str):
        """Extract metadata from folder path structure.

        Examples:
        - /WSOP ARCHIVE (PRE-2016)/WSOP 2012/... -> year=2012
        - /WSOP Bracelet Event/WSOP-LAS VEGAS/2024 WSOP-LAS VEGAS/... -> year=2024, venue=LAS VEGAS
        - /WSOP-EUROPE/2024 WSOP-Europe/... -> year=2024, venue=EUROPE
        """
        path_parts = file_path.replace('\\', '/').split('/')

        # Find the deepest year folder for event grouping
        year_folder_idx = -1
        event_folder_idx = -1

        for i, part in enumerate(path_parts):
            # Extract year from folder name (e.g., "WSOP 2012", "2024 WSOP-LAS VEGAS")
            year_match = re.search(r'\b(19[7-9]\d|20[0-2]\d)\b', part)
            if year_match:
                if parsed.year is None:
                    parsed.year = int(year_match.group(1))
                year_folder_idx = i

            # Extract event number from folder name (e.g., "Event #14", "Event 21")
            event_match = re.search(r'Event\s*#?(\d+)', part, re.IGNORECASE)
            if event_match:
                if parsed.event_number is None:
                    parsed.event_number = int(event_match.group(1))
                event_folder_idx = i

            # Extract title from event folder (e.g., "$25K No-Limit Hold'em")
            if 'Event' in part and '$' in part:
                title_match = re.search(r'\$[\d.]+[KMB]?\s+(.+?)(?:\s*\/|$)', part)
                if title_match and parsed.title is None:
                    parsed.title = title_match.group(1).strip()

        # Generate event_key for grouping files into the same event
        # Strategy: Use the folder path up to and including the event/year folder
        if event_folder_idx >= 0:
            # If we found an event folder, use path up to that folder
            parsed.event_key = '/'.join(path_parts[:event_folder_idx + 1])
        elif year_folder_idx >= 0:
            # If only year folder found, use path up to year + 1 level (to differentiate by subfolder)
            end_idx = min(year_folder_idx + 2, len(path_parts) - 1)
            parsed.event_key = '/'.join(path_parts[:end_idx])
        else:
            # Fallback: use parent folder
            parsed.event_key = '/'.join(path_parts[:-1])

        # Set title from meaningful folder if not already set
        for i in range(len(path_parts) - 2, -1, -1):  # Skip filename
            part = path_parts[i]
            if 'Event' in part or 'MAIN' in part.upper() or 'Day' in part:
                if parsed.title is None:
                    parsed.title = part
                break

    def _detect_version_type(self, filename: str) -> str:
        """Detect version type from filename"""
        for version, pattern in self.VERSION_PATTERNS.items():
            if pattern.search(filename):
                return version
        return 'generic'

    def _parse_wsop(self, parsed: ParsedFile, filename: str):
        """Parse WSOP filename with multiple pattern support"""

        # Pattern 1: Bracelet pattern (e.g., 1-wsop-2024-be-ev-21-25k-nlh-hr-ft-title.mp4)
        match = self.WSOP_BRACELET_PATTERN.match(filename)
        if match:
            parsed.episode_number = int(match.group(1))
            parsed.year = int(match.group(2))
            parsed.event_number = int(match.group(3))

            buy_in_str = match.group(4).lower()
            if 'k' in buy_in_str:
                parsed.buy_in = int(buy_in_str.replace('k', '')) * 1000
            else:
                parsed.buy_in = int(buy_in_str)

            game = match.group(5).lower()
            mapped_game = self.GAME_TYPES.get(game)
            if mapped_game in self.VALID_GAME_TYPES:
                parsed.game_type = mapped_game

            if match.group(7):
                table = match.group(7).lower()
                mapped_type = self.TABLE_TYPES.get(table)
                if mapped_type in self.VALID_TABLE_TYPES:
                    parsed.table_type = mapped_type

            if match.group(8):
                parsed.title = match.group(8).replace('-', ' ').title()

            parsed.event_type = 'bracelet'
            return

        # Pattern 2: Circuit pattern (e.g., WCLA24-15.mp4, WE24-ME-11.mp4)
        match = self.WSOP_CIRCUIT_PATTERN.match(filename)
        if match:
            parsed.year = 2000 + int(match.group(2))
            parsed.episode_number = int(match.group(3))
            parsed.event_type = 'circuit'
            return

        # Pattern 3: WSOP_YEAR_EP pattern (e.g., WSOP_2008_01.mp4) - more specific, check first
        year_ep_match = re.match(r'^WSOP[_-](\d{4})[_-](\d+)', filename, re.IGNORECASE)
        if year_ep_match:
            parsed.year = int(year_ep_match.group(1))
            parsed.episode_number = int(year_ep_match.group(2))
            return

        # Pattern 4: WSOP13_ME21 pattern (e.g., WSOP13_ME21_NB.mp4)
        short_match = re.match(r'^WSOP(\d{2})[_-]?(ME)?(\d+)', filename, re.IGNORECASE)
        if short_match:
            parsed.year = 2000 + int(short_match.group(1))
            if short_match.group(2):  # ME = Main Event
                parsed.event_type = 'main_event'
            parsed.episode_number = int(short_match.group(3))
            return

        # Pattern 5: Show pattern (e.g., WS12_Show_26_ME22_NB.mp4)
        show_match = re.match(r'^WS(\d{2})_(?:Show_)?(\d+)_?(.+)?\.', filename, re.IGNORECASE)
        if show_match:
            parsed.year = 2000 + int(show_match.group(1))
            parsed.episode_number = int(show_match.group(2))
            return

        # Pattern 6: Archive pattern (e.g., wsop-1979-me-nobug.mp4, WSOP - 1973.mp4) - generic, last
        archive_match = re.match(r'^(?:wsop|WSOP)[\s_-]*(\d{4})(?:[\s_-]*(me|ME))?', filename, re.IGNORECASE)
        if archive_match:
            parsed.year = int(archive_match.group(1))
            if archive_match.group(2):  # ME = Main Event
                parsed.event_type = 'main_event'
                parsed.event_number = 1  # Main Event is typically event #1
            return

    def _parse_ggmillions(self, parsed: ParsedFile, filename: str):
        """Parse GGMillions filename"""
        match = self.GGMILLIONS_PATTERN.match(filename)
        if match:
            date_str = match.group(1)
            parsed.year = 2000 + int(date_str[:2])
            parsed.title = match.group(2)
            parsed.event_type = 'super_high_roller'

    def _parse_gog(self, parsed: ParsedFile, filename: str):
        """Parse Game of Gold filename"""
        match = self.GOG_PATTERN.match(filename)
        if match:
            parsed.episode_number = int(match.group(1))
            # Keep underscores for DB constraint compliance (final_edit, not final edit)
            version = match.group(2).lower()
            # Map known versions to valid DB values
            version_map = {'final_edit': 'final_edit', 'clean': 'clean', 'mastered': 'mastered'}
            parsed.version_type = version_map.get(version, 'generic')
            date_str = match.group(3)
            parsed.year = int(date_str[:4])
            parsed.event_type = 'tv_series'

    def _parse_pad(self, parsed: ParsedFile, filename: str):
        """Parse Poker After Dark filename"""
        match = self.PAD_PATTERN.match(filename)
        if match:
            # Season number maps to year approximately
            season = int(match.group(1))
            parsed.year = 2006 + season  # PAD started in 2007
            parsed.episode_number = int(match.group(2))
            parsed.event_type = 'tv_series'

    def _parse_mpp(self, parsed: ParsedFile, filename: str):
        """Parse Mystery Poker Pro filename"""
        match = self.MPP_PATTERN.match(filename)
        if match:
            # Parse GTD amount
            gtd = match.group(1).upper()
            if 'M' in gtd:
                parsed.buy_in = int(float(gtd.replace('M', '')) * 1000000)
            elif 'K' in gtd:
                parsed.buy_in = int(float(gtd.replace('K', '')) * 1000)

            parsed.title = match.group(3)
            parsed.event_type = 'mystery_bounty'

    def _parse_hcl(self, parsed: ParsedFile, filename: str):
        """Parse Hustler Casino Live filename"""
        match = self.HCL_PATTERN.match(filename)
        if match:
            parsed.year = int(match.group(1))
            parsed.title = match.group(4).replace('_', ' ')
            parsed.event_type = 'cash_game'


class NasSyncService:
    """
    NAS synchronization service.
    Scans NAS directories and upserts video files to database.
    """

    # Project code to NAS path mapping
    # Docker container path (mounted from Z: drive)
    NAS_PATHS = {
        'WSOP': '/nas/ARCHIVE/WSOP',
        'GGMILLIONS': '/nas/ARCHIVE/GGMillions',
        'MPP': '/nas/ARCHIVE/MPP',
        'PAD': '/nas/ARCHIVE/PAD',
        'GOG': '/nas/ARCHIVE/GOG 최종',
        'HCL': '/nas/ARCHIVE/HCL',
    }

    # Windows fallback paths (for local development)
    NAS_PATHS_WINDOWS = {
        'WSOP': r'Z:\GGPNAs\ARCHIVE\WSOP',
        'GGMILLIONS': r'Z:\GGPNAs\ARCHIVE\GGMillions',
        'MPP': r'Z:\GGPNAs\ARCHIVE\MPP',
        'PAD': r'Z:\GGPNAs\ARCHIVE\PAD',
        'GOG': r'Z:\GGPNAs\ARCHIVE\GOG 최종',
        'HCL': r'Z:\GGPNAs\ARCHIVE\HCL',
    }

    def __init__(self, db: Session):
        self.db = db
        self.parser = FileParser()
        self.file_filter = FileFilter()
        self.title_generator = get_title_generator()
        self.catalog_title_generator = get_catalog_title_generator()

    def scan_project(
        self,
        project_code: str,
        custom_path: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> ScanResult:
        """
        Scan a project's NAS directory and sync to database.

        Args:
            project_code: Project code (WSOP, HCL, etc.)
            custom_path: Override NAS path (for testing)
            limit: Max files to process (for testing)

        Returns:
            ScanResult with counts and status
        """
        result = ScanResult(project_code=project_code)

        # Get project from DB
        project = self.db.execute(
            select(Project).where(Project.code == project_code)
        ).scalar_one_or_none()

        if not project:
            result.status = 'error'
            result.errors.append(f"Project not found: {project_code}")
            return result

        # Determine scan path (try Docker path first, then Windows fallback)
        scan_path = custom_path
        if not scan_path:
            # Try Docker container path first
            docker_path = self.NAS_PATHS.get(project_code)
            windows_path = self.NAS_PATHS_WINDOWS.get(project_code)

            if docker_path and os.path.exists(docker_path):
                scan_path = docker_path
            elif windows_path and os.path.exists(windows_path):
                scan_path = windows_path
            else:
                result.status = 'error'
                result.errors.append(f"No accessible NAS path for: {project_code}")
                result.errors.append(f"Tried: {docker_path}, {windows_path}")
                return result

        # Final check
        if not os.path.exists(scan_path):
            result.status = 'error'
            result.errors.append(f"Path not accessible: {scan_path}")
            return result

        # Scan files
        files = self._scan_directory(scan_path, limit)
        result.scanned_count = len(files)

        if not files:
            return result

        # Process files in batches
        batch_size = 100
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            new, updated, errors = self._process_batch(batch, project)
            result.new_count += new
            result.updated_count += updated
            result.error_count += len(errors)
            result.errors.extend(errors)

        return result

    def _scan_directory(
        self,
        path: str,
        limit: Optional[int] = None,
    ) -> List[str]:
        """Recursively scan directory for video files"""
        files = []

        for root, dirs, filenames in os.walk(path):
            for filename in filenames:
                ext = Path(filename).suffix.lower()
                if ext in FileParser.VIDEO_EXTENSIONS:
                    files.append(os.path.join(root, filename))

                    if limit and len(files) >= limit:
                        return files

        return files

    def _process_batch(
        self,
        file_paths: List[str],
        project: Project,
    ) -> tuple[int, int, List[str]]:
        """Process a batch of files"""
        new_count = 0
        updated_count = 0
        errors = []

        for file_path in file_paths:
            try:
                # Check file filter first
                filter_result = self.file_filter.check_file(file_path)

                parsed = self.parser.parse(file_path, project.code)

                # Find or create episode (only if not hidden)
                if filter_result.is_hidden:
                    # Hidden files don't need episode grouping
                    episode_id = None
                else:
                    episode_id = self._get_or_create_episode(parsed, project)

                # Upsert video file with filter result
                is_new = self._upsert_video_file(parsed, episode_id, filter_result)

                if is_new:
                    new_count += 1
                else:
                    updated_count += 1

            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")

        self.db.commit()
        return new_count, updated_count, errors

    def _get_or_create_episode(
        self,
        parsed: ParsedFile,
        project: Project,
    ) -> Optional[UUID]:
        """Find or create an episode for the video file"""

        # Find season
        season = self.db.execute(
            select(Season)
            .where(Season.project_id == project.id)
            .where(Season.year == parsed.year if parsed.year else True)
            .order_by(Season.year.desc())
        ).scalars().first()

        if not season:
            # Create default season if none exists
            season = Season(
                id=uuid4(),
                project_id=project.id,
                year=parsed.year or datetime.now().year,
                name=f"{project.code} {parsed.year or datetime.now().year}",
                status='active',
            )
            self.db.add(season)
            self.db.flush()

        # Find event - use event_number first, then event_key (folder-based grouping)
        event = None

        if parsed.event_number:
            # Primary lookup: by event_number (most reliable)
            event = self.db.execute(
                select(Event)
                .where(Event.season_id == season.id)
                .where(Event.event_number == parsed.event_number)
            ).scalars().first()
        elif parsed.event_key:
            # Secondary lookup: by event_key hash stored in name_short field
            # Use MD5 hash (32 chars) to fit in VARCHAR(100)
            event_key_hash = hashlib.md5(parsed.event_key.encode()).hexdigest()
            event = self.db.execute(
                select(Event)
                .where(Event.season_id == season.id)
                .where(Event.name_short == event_key_hash)
            ).scalars().first()

        if not event:
            # Generate a stable event_number for grouping
            if not parsed.event_number and parsed.event_key:
                # Get next event number for this season
                max_event = self.db.execute(
                    select(func.max(Event.event_number))
                    .where(Event.season_id == season.id)
                ).scalar() or 0
                event_number = max_event + 1
            else:
                event_number = parsed.event_number or 1

            # Create event with event_key hash stored in name_short for future lookups
            event_key_hash = hashlib.md5(parsed.event_key.encode()).hexdigest() if parsed.event_key else None

            event = Event(
                id=uuid4(),
                season_id=season.id,
                event_number=event_number,
                name=parsed.title or f"Event {event_number}",
                name_short=event_key_hash,  # Store hash for grouping (32 chars)
                event_type=parsed.event_type,
                game_type=parsed.game_type,
                buy_in=parsed.buy_in,
                status='completed',
            )
            self.db.add(event)
            self.db.flush()

        # Find episode
        episode = None
        if parsed.episode_number:
            episode = self.db.execute(
                select(Episode)
                .where(Episode.event_id == event.id)
                .where(Episode.episode_number == parsed.episode_number)
            ).scalar_one_or_none()
        elif parsed.day_number:
            episode = self.db.execute(
                select(Episode)
                .where(Episode.event_id == event.id)
                .where(Episode.day_number == parsed.day_number)
            ).scalar_one_or_none()

        if not episode:
            # Create episode
            episode = Episode(
                id=uuid4(),
                event_id=event.id,
                episode_number=parsed.episode_number,
                day_number=parsed.day_number,
                part_number=parsed.part_number,
                title=parsed.title or parsed.file_name,
                table_type=parsed.table_type,
                episode_type='full',
            )
            self.db.add(episode)
            self.db.flush()

        return episode.id

    def _upsert_video_file(
        self,
        parsed: ParsedFile,
        episode_id: Optional[UUID],
        filter_result: Optional[FilterResult] = None,
    ) -> bool:
        """Insert or update video file record. Returns True if new."""

        # Check if exists
        existing = self.db.execute(
            select(VideoFile).where(VideoFile.file_path == parsed.file_path)
        ).scalar_one_or_none()

        # Determine hidden status
        is_hidden = filter_result.is_hidden if filter_result else False
        hidden_reason = filter_result.hidden_reason if filter_result else None

        # Generate display title
        display_title = self.title_generator.generate(
            parsed.file_name,
            parsed.project_code,
            parsed.year
        )

        if existing:
            # Update
            existing.file_size_bytes = parsed.file_size
            existing.file_mtime = parsed.modified_time
            existing.episode_id = episode_id
            existing.version_type = parsed.version_type
            existing.scan_status = 'scanned'
            existing.is_hidden = is_hidden
            existing.hidden_reason = hidden_reason
            existing.display_title = display_title
            return False
        else:
            # Insert
            video_file = VideoFile(
                id=uuid4(),
                episode_id=episode_id,
                file_path=parsed.file_path,
                file_name=parsed.file_name,
                file_size_bytes=parsed.file_size,
                file_mtime=parsed.modified_time,
                file_format=Path(parsed.file_name).suffix.lower().lstrip('.'),
                resolution=parsed.resolution,
                video_codec=parsed.video_codec,
                audio_codec=parsed.audio_codec,
                bitrate_kbps=parsed.bitrate_kbps,
                duration_seconds=parsed.duration_seconds,
                version_type=parsed.version_type,
                is_original=parsed.version_type == 'generic',
                scan_status='scanned',
                is_hidden=is_hidden,
                hidden_reason=hidden_reason,
                display_title=display_title,
            )
            self.db.add(video_file)
            return True

    def update_display_titles(self) -> Dict[str, Any]:
        """
        Update display_title for all video files that don't have one.
        Used for migrating existing data.
        """
        # Get all files without display_title
        files = self.db.execute(
            select(VideoFile)
            .where(VideoFile.display_title.is_(None))
        ).scalars().all()

        updated = 0
        errors = []

        for vf in files:
            try:
                # Determine project code from file path
                project_code = self._detect_project_from_path(vf.file_path)

                # Extract year from path if possible
                year = self._extract_year_from_path(vf.file_path)

                # Generate title
                display_title = self.title_generator.generate(
                    vf.file_name,
                    project_code,
                    year
                )

                vf.display_title = display_title
                updated += 1

            except Exception as e:
                errors.append(f"{vf.file_name}: {str(e)}")

        self.db.commit()

        return {
            'total': len(files),
            'updated': updated,
            'errors': len(errors),
            'error_details': errors[:10]  # First 10 errors
        }

    def _detect_project_from_path(self, file_path: str) -> str:
        """Detect project code from file path"""
        path_lower = file_path.lower()

        if 'wsop' in path_lower:
            return 'WSOP'
        elif 'ggmillions' in path_lower:
            return 'GGMILLIONS'
        elif 'gog' in path_lower:
            return 'GOG'
        elif 'pad' in path_lower:
            return 'PAD'
        elif 'mpp' in path_lower:
            return 'MPP'
        elif 'hcl' in path_lower:
            return 'HCL'
        else:
            return 'OTHER'

    def _extract_year_from_path(self, file_path: str) -> Optional[int]:
        """Extract year from file path"""
        import re
        match = re.search(r'\b(19[7-9]\d|20[0-2]\d)\b', file_path)
        if match:
            return int(match.group(1))
        return None

    def get_scan_status(self) -> Dict[str, Any]:
        """Get current sync status for all projects"""
        status = {}

        for code in self.NAS_PATHS.keys():
            project = self.db.execute(
                select(Project).where(Project.code == code)
            ).scalar_one_or_none()

            if project:
                video_count = self.db.execute(
                    select(func.count(VideoFile.id))
                    .join(Episode)
                    .join(Event)
                    .join(Season)
                    .where(Season.project_id == project.id)
                ).scalar() or 0

                status[code] = {
                    'project_id': str(project.id),
                    'nas_path': self.NAS_PATHS.get(code),
                    'video_count': video_count,
                }

        return status

    def update_catalog_titles(self) -> Dict[str, Any]:
        """
        Update catalog_title, episode_title, and content_type for all video files.
        Used for migrating existing data to the new catalog system.
        """
        # Get all visible files
        files = self.db.execute(
            select(VideoFile)
            .where(VideoFile.is_hidden == False)
        ).scalars().all()

        updated = 0
        errors = []

        for vf in files:
            try:
                # Determine project code from file path
                project_code = self._detect_project_from_path(vf.file_path)

                # Extract year from path if possible
                year = self._extract_year_from_path(vf.file_path)

                # Get event name if available through relationships
                event_name = None
                if vf.episode and vf.episode.event:
                    event_name = vf.episode.event.name

                # Generate catalog titles
                catalog_result = self.catalog_title_generator.generate(
                    vf.file_name,
                    project_code,
                    year,
                    event_name
                )

                vf.content_type = catalog_result.content_type
                vf.catalog_title = catalog_result.catalog_title
                vf.episode_title = catalog_result.episode_title
                updated += 1

            except Exception as e:
                errors.append(f"{vf.file_name}: {str(e)}")

        self.db.commit()

        return {
            'total': len(files),
            'updated': updated,
            'errors': len(errors),
            'error_details': errors[:10]
        }

    def update_catalog_items(self) -> Dict[str, Any]:
        """
        Set is_catalog_item=True for representative files.
        Uses version_type priority to select one file per catalog_title + episode_title.

        Priority: stream > clean > final_edit > mastered > nobug > generic > pgm > hires
        """
        # Version type priority (lower is better)
        version_priority = {
            'stream': 1,
            'clean': 2,
            'final_edit': 3,
            'mastered': 4,
            'nobug': 5,
            'generic': 6,
            'pgm': 7,
            'hires': 8,
        }

        # Reset all catalog items
        self.db.execute(
            VideoFile.__table__.update().values(is_catalog_item=False)
        )

        # Get all visible files grouped by catalog_title + episode_title
        files = self.db.execute(
            select(VideoFile)
            .where(VideoFile.is_hidden == False)
            .where(VideoFile.catalog_title.isnot(None))
            .order_by(VideoFile.catalog_title, VideoFile.episode_title)
        ).scalars().all()

        # Group by catalog_title + episode_title
        groups = {}
        for vf in files:
            key = (vf.catalog_title, vf.episode_title)
            if key not in groups:
                groups[key] = []
            groups[key].append(vf)

        # Select best version for each group
        selected_count = 0
        for key, group in groups.items():
            # Sort by version priority (lower is better), then by file size (larger is better)
            sorted_group = sorted(
                group,
                key=lambda x: (
                    version_priority.get(x.version_type, 99),
                    -(x.file_size_bytes or 0)
                )
            )

            # Mark best version as catalog item
            best = sorted_group[0]
            best.is_catalog_item = True
            selected_count += 1

        self.db.commit()

        return {
            'total_files': len(files),
            'total_groups': len(groups),
            'catalog_items': selected_count,
            'duplicates_removed': len(files) - selected_count
        }
