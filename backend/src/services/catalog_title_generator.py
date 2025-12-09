"""
Catalog Title Generator Service

Generates catalog_title and episode_title from video filenames.
Separates "where to find" (catalog) from "what to watch" (episode).
"""
import re
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class CatalogTitles:
    """Generated catalog and episode titles"""
    content_type: str       # full_episode, hand_clip, highlight, etc.
    catalog_title: str      # Group title: "WSOP 2024 Main Event"
    episode_title: str      # Item title: "Day 1A" or "Ding vs Boianovsky"


class CatalogTitleGenerator:
    """
    Generate catalog_title and episode_title from video filenames.

    Catalog Structure:
    - Full Episode: [대회명] [연도] [이벤트명] → [날짜/세션]
    - Hand Clip: [대회명] [연도] [이벤트명] [날짜] → [플레이어 vs 플레이어]

    Examples:
        "2024 WSOP Paradise Super Main Event - Day 1C.mp4"
        → catalog: "WSOP 2024 Paradise Super Main Event"
        → episode: "Day 1C"

        "1213_Hand_46_Ding 64c vs Boianovsky AsQh_Clean.mp4"
        → catalog: "WSOP 2024 Main Event Day 3"
        → episode: "Ding vs Boianovsky"

        "E08_GOG_final_edit_20231120.mp4"
        → catalog: "Game of Gold Season 1"
        → episode: "Episode 8"
    """

    # Content type detection patterns
    HAND_CLIP_PATTERNS = [
        r'_Hand_\d+_',           # Hand clip format
        r'\s+vs\s+',             # Player vs Player
        r'_vs_',                 # underscore vs format
    ]

    HIGHLIGHT_PATTERNS = [
        r'highlight',
        r'best\s*of',
        r'top\s*\d+',
    ]

    INTERVIEW_PATTERNS = [
        r'interview',
    ]

    RECAP_PATTERNS = [
        r'recap',
        r'summary',
    ]

    # Folder name pattern: N-wsop-YYYY-TYPE-ev-NN-BUYIN-EVENT
    # Example: 6-wsop-2024-be-ev-10-10k-omaha-hi-lo-championship
    # Also handles: 12-wsop-2024-be-ev-20-300-gladiators (no 'k' suffix)
    # Captures event name up to first episode marker (-ft-, -day\d+-, etc.)
    FOLDER_PATTERN = re.compile(
        r'^(\d+)-wsop-(\d{4})-([a-z]+)-ev-(\d+)-(\d+k?)-([a-z0-9-]+?)(?:-(ft|day\d+)-.+)?$',
        re.IGNORECASE
    )

    # Alternative folder pattern for full event name (when no episode marker)
    FOLDER_PATTERN_FULL = re.compile(
        r'^(\d+)-wsop-(\d{4})-([a-z]+)-ev-(\d+)-(\d+k?)-([a-z0-9-]+)$',
        re.IGNORECASE
    )

    # Short Main Event pattern: N-wsop-YYYY-me (standalone)
    ME_SHORT_PATTERN = re.compile(
        r'^(\d+)-wsop-(\d{4})-me$',
        re.IGNORECASE
    )

    # Main Event with episode marker: N-wsop-YYYY-me-dayN-description or N-wsop-YYYY-me-ft-description
    ME_WITH_EPISODE_PATTERN = re.compile(
        r'^(\d+)-wsop-(\d{4})-me-(day\d+[a-z]?|ft)-(.+)$',
        re.IGNORECASE
    )

    # WSOP Europe pattern: wsope-YYYY-BUYIN-EVENT-ft-NNN
    WSOPE_PATTERN = re.compile(
        r'^wsope-(\d{4})-(\d+)-([a-z0-9]+)(?:-(ft|day\d+)-(.+))?$',
        re.IGNORECASE
    )

    # Legacy folder pattern: e-YYYY-BUYIN-EVENT
    # Example: e-2021-10k-me or e-2021-1650-nlh6max (non-k buyin)
    LEGACY_FOLDER_PATTERN = re.compile(
        r'^e-(\d{4})-(\d+k?)-(.+)$',
        re.IGNORECASE
    )

    # Event type mapping
    EVENT_TYPE_MAP = {
        'be': 'Bracelet Event',
        'ce': 'Circuit Event',
        'sce': 'Super Circuit Event',
    }

    # Game variant mapping
    VARIANT_MAP = {
        'nlh': 'NLH',
        'nlh6max': 'NLH 6-Max',
        'plo': 'PLO',
        'stud': 'Stud',
        'razz': 'Razz',
        'horse': 'H.O.R.S.E.',
        'hr': 'High Roller',
        'shr': 'Super High Roller',
        'me': 'Main Event',
        '6max': '6-Max',
        '27td': 'Triple Draw',
        'ppc': 'Poker Players Championship',
        'omaha': 'Omaha',
        'platinumhighroller': 'Platinum High Roller',
        'platinum': 'Platinum',
        'highroller': 'High Roller',
        'superturbo': 'Super Turbo',
        'bounty': 'Bounty',
        'shootout': 'Shootout',
        'championship': 'Championship',
        'gladiators': 'Gladiators',
        'kickoff': 'Kickoff',
        'mystery': 'Mystery',
        'millions': 'Millions',
        'reunion': 'Reunion',
        'champions': 'Champions',
    }

    # Day code to Day name mapping (WSOP Main Event 2024)
    # 1211 = Dec 11 = Day 1A, 1212 = Day 1B, etc.
    WSOP_2024_DAY_MAP = {
        '1211': 'Day 1A',
        '1212': 'Day 1B',
        '1213': 'Day 2',
        '1214': 'Day 3',
        '1215': 'Day 4',
        '1216': 'Day 5',
        '1217': 'Day 6',
        '1218': 'Day 7',
        '1219': 'Final Table',
    }

    def generate(
        self,
        filename: str,
        project_code: str,
        year: Optional[int] = None,
        event_name: Optional[str] = None
    ) -> CatalogTitles:
        """
        Generate catalog and episode titles from filename.

        Args:
            filename: Original filename (with or without extension)
            project_code: Project code (WSOP, HCL, GOG, etc.)
            year: Year from season or folder
            event_name: Event name from database if available

        Returns:
            CatalogTitles with content_type, catalog_title, episode_title
        """
        # Remove extension
        name = re.sub(r'\.[a-zA-Z0-9]+$', '', filename)

        # Detect content type
        content_type = self._detect_content_type(name)

        # Generate based on project
        if project_code == 'WSOP':
            return self._generate_wsop(name, year, content_type, event_name)
        elif project_code == 'GOG':
            return self._generate_gog(name, year, content_type)
        elif project_code == 'PAD':
            return self._generate_pad(name, year, content_type)
        elif project_code == 'GGMILLIONS':
            return self._generate_ggmillions(name, year, content_type)
        elif project_code == 'MPP':
            return self._generate_mpp(name, year, content_type)
        elif project_code == 'HCL':
            return self._generate_hcl(name, year, content_type)
        else:
            return self._generate_generic(name, project_code, year, content_type)

    def _detect_content_type(self, name: str) -> str:
        """Detect content type from filename"""
        name_lower = name.lower()

        # Check hand clip patterns
        for pattern in self.HAND_CLIP_PATTERNS:
            if re.search(pattern, name, re.IGNORECASE):
                return 'hand_clip'

        # Check highlight patterns
        for pattern in self.HIGHLIGHT_PATTERNS:
            if re.search(pattern, name_lower):
                return 'highlight'

        # Check interview patterns
        for pattern in self.INTERVIEW_PATTERNS:
            if re.search(pattern, name_lower):
                return 'interview'

        # Check recap patterns
        for pattern in self.RECAP_PATTERNS:
            if re.search(pattern, name_lower):
                return 'recap'

        return 'full_episode'

    def _generate_wsop(
        self,
        name: str,
        year: Optional[int],
        content_type: str,
        event_name: Optional[str]
    ) -> CatalogTitles:
        """Generate WSOP catalog/episode titles"""

        # First, check WSOP Europe pattern: wsope-YYYY-BUYIN-EVENT-ft-NNN
        wsope_match = self.WSOPE_PATTERN.match(name)
        if wsope_match:
            yr = year or int(wsope_match.group(1))
            buyin = wsope_match.group(2)
            event_code = wsope_match.group(3)
            marker = wsope_match.group(4)  # ft or dayN
            ep_num = wsope_match.group(5)  # 010

            # Format buyin
            if len(buyin) >= 4:
                formatted_buyin = f"${int(buyin):,}"
            else:
                formatted_buyin = f"${buyin}"

            # Format event name
            event_name_clean = self.VARIANT_MAP.get(event_code.lower(), event_code.upper())

            catalog = f"WSOP Europe {yr} {formatted_buyin} {event_name_clean}"

            if marker and ep_num:
                episode = f"{marker.title()} - Part {ep_num}"
            else:
                episode = self._clean_for_episode(name)

            return CatalogTitles(
                content_type=content_type,
                catalog_title=catalog,
                episode_title=episode
            )

        # Check Main Event pattern with episode: N-wsop-YYYY-me-dayN-description
        me_with_ep = self.ME_WITH_EPISODE_PATTERN.match(name)
        if me_with_ep:
            yr = year or int(me_with_ep.group(2))
            day_marker = me_with_ep.group(3).title()  # day1D → Day1D
            description = me_with_ep.group(4).replace('-', ' ').title()

            catalog = f"WSOP {yr} Main Event"
            episode = f"{day_marker} - {description}"

            return CatalogTitles(
                content_type=content_type,
                catalog_title=catalog,
                episode_title=episode
            )

        # Try to parse folder-style event names in the FILENAME itself
        # Example: "1-wsop-2024-be-ev-01-5k-champions-reunion-ft-Conniff-hero-calls.mp4"
        parsed_event = self._parse_wsop_folder_event(name)
        if parsed_event:
            yr = year or parsed_event.get('year', 2024)
            catalog = f"WSOP {yr} {parsed_event['event_name']}"
            # Extract episode from the part after the folder pattern
            episode = self._extract_episode_from_folder_filename(name)
            return CatalogTitles(
                content_type=content_type,
                catalog_title=catalog,
                episode_title=episode
            )

        # Also try event_name if provided (might come from DB)
        if event_name:
            # Check if event_name itself is a Main Event with episode pattern
            me_event = self.ME_WITH_EPISODE_PATTERN.match(event_name)
            if me_event:
                yr = year or int(me_event.group(2))
                return CatalogTitles(
                    content_type=content_type,
                    catalog_title=f"WSOP {yr} Main Event",
                    episode_title=self._clean_for_episode(name)
                )

            parsed_from_event = self._parse_wsop_folder_event(event_name)
            if parsed_from_event:
                yr = year or parsed_from_event.get('year', 2024)
                catalog = f"WSOP {yr} {parsed_from_event['event_name']}"
                episode = self._clean_for_episode(name)
                return CatalogTitles(
                    content_type=content_type,
                    catalog_title=catalog,
                    episode_title=episode
                )

        # Hand clip format: 1213_Hand_46_Ding 64c vs Boianovsky AsQh_Clean
        hand_match = re.match(r'^(\d{4})_Hand_(\d+)_(.+?)_(Clean|PGM|Stream)', name, re.IGNORECASE)
        if hand_match:
            date_code = hand_match.group(1)
            hand_num = hand_match.group(2)
            players_raw = hand_match.group(3)

            # Get day from date code
            day = self.WSOP_2024_DAY_MAP.get(date_code, f"Day {date_code}")

            # Extract player names (remove cards)
            players = self._extract_player_names(players_raw)

            yr = year or 2024
            catalog = f"WSOP {yr} Main Event {day}"
            episode = players

            return CatalogTitles(
                content_type='hand_clip',
                catalog_title=catalog,
                episode_title=episode
            )

        # Full episode with Day: "2024 WSOP Paradise Super Main Event - Day 1C"
        day_match = re.search(r'(.+?)\s*[-–]\s*(Day\s*\d+[A-Z]?|Final\s*Table|FT)\b', name, re.IGNORECASE)
        if day_match:
            event_part = day_match.group(1).strip()
            day_part = day_match.group(2).strip()

            # Clean event name
            event_clean = re.sub(r'^\d{4}\s*', '', event_part)  # Remove leading year
            event_clean = re.sub(r'^WSOP\s*', '', event_clean, flags=re.IGNORECASE)
            event_clean = event_clean.strip()

            yr = year or self._extract_year(event_part) or 2024

            if event_clean:
                catalog = f"WSOP {yr} {event_clean}"
            else:
                catalog = f"WSOP {yr}"

            # Normalize day format
            episode = day_part.replace('FT', 'Final Table')

            return CatalogTitles(
                content_type='full_episode',
                catalog_title=catalog,
                episode_title=episode
            )

        # WSOP Europe format: #WSOPE 2024 NLH MAIN EVENT DAY 1B BRACELET EVENT #13
        wsope_match = re.match(r'#?WSOP[E]?\s*(\d{4})\s*(.+?)\s*(DAY\s*\d+[A-Z]?|Final)', name, re.IGNORECASE)
        if wsope_match:
            yr = int(wsope_match.group(1))
            event_part = wsope_match.group(2).strip()
            day_part = wsope_match.group(3).strip()

            catalog = f"WSOP Europe {yr} {event_part}"
            episode = day_part

            return CatalogTitles(
                content_type='full_episode',
                catalog_title=catalog,
                episode_title=episode
            )

        # WS12_Show_24_ME20_NB format (old archive)
        show_match = re.match(r'^WS(\d{2})_Show_(\d+)_?(.+)?', name, re.IGNORECASE)
        if show_match:
            yr = 2000 + int(show_match.group(1))
            show_num = show_match.group(2)

            catalog = f"WSOP {yr}"
            episode = f"Show {show_num}"

            return CatalogTitles(
                content_type='full_episode',
                catalog_title=catalog,
                episode_title=episode
            )

        # WSOP13_ME19_NB format
        short_match = re.match(r'^WSOP(\d{2})[_-]?(ME)?(\d+)', name, re.IGNORECASE)
        if short_match:
            yr = 2000 + int(short_match.group(1))
            is_me = short_match.group(2)
            ep = int(short_match.group(3))

            if is_me:
                catalog = f"WSOP {yr} Main Event"
            else:
                catalog = f"WSOP {yr}"
            episode = f"Episode {ep}"

            return CatalogTitles(
                content_type='full_episode',
                catalog_title=catalog,
                episode_title=episode
            )

        # Fallback: use event_name if available
        yr = year or 2024
        if event_name:
            # Clean event_name (remove extension if present)
            clean_event = re.sub(r'\.[a-zA-Z0-9]+$', '', event_name)
            # Also clean common suffixes
            clean_event = re.sub(r'[_-]?(clean|nobug|nb|pgm|hires|stream|mastered|final_edit)$', '', clean_event, flags=re.IGNORECASE)
            catalog = f"WSOP {yr} {clean_event}"
        else:
            catalog = f"WSOP {yr}"

        # Clean catalog of any remaining extensions
        catalog = re.sub(r'\.[a-zA-Z0-9]+$', '', catalog)

        # Try to extract episode from filename
        episode = self._clean_for_episode(name)

        return CatalogTitles(
            content_type=content_type,
            catalog_title=catalog,
            episode_title=episode
        )

    def _generate_gog(self, name: str, year: Optional[int], content_type: str) -> CatalogTitles:
        """Generate Game of Gold catalog/episode titles"""

        # E08_GOG_final_edit_20231120
        match = re.match(r'^E(\d+)_GOG', name, re.IGNORECASE)
        if match:
            ep_num = int(match.group(1))
            # Season 1 for 2023, Season 2 for later
            season = 1 if (year and year <= 2023) else (2 if year and year > 2023 else 1)

            return CatalogTitles(
                content_type='full_episode',
                catalog_title=f"Game of Gold Season {season}",
                episode_title=f"Episode {ep_num}"
            )

        return CatalogTitles(
            content_type=content_type,
            catalog_title="Game of Gold",
            episode_title=self._clean_for_episode(name)
        )

    def _generate_pad(self, name: str, year: Optional[int], content_type: str) -> CatalogTitles:
        """Generate Poker After Dark catalog/episode titles"""

        # pad-s12-ep11-020 or PAD S12 E01
        match = re.match(r'^PAD[\s_-]*S(\d+)[\s_-]*E[Pp]?(\d+)', name, re.IGNORECASE)
        if match:
            season = int(match.group(1))
            ep = int(match.group(2))

            return CatalogTitles(
                content_type='full_episode',
                catalog_title=f"Poker After Dark Season {season}",
                episode_title=f"Episode {ep}"
            )

        return CatalogTitles(
            content_type=content_type,
            catalog_title="Poker After Dark",
            episode_title=self._clean_for_episode(name)
        )

    def _generate_ggmillions(self, name: str, year: Optional[int], content_type: str) -> CatalogTitles:
        """Generate GG Millions catalog/episode titles"""

        # 250611_Super High Roller Poker FINAL TABLE with Rayan Chamas
        match = re.match(r'^(\d{6})_(.+)', name)
        if match:
            date_str = match.group(1)
            title = match.group(2)

            # Parse date
            yr = 2000 + int(date_str[:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])

            # Extract player name if present
            player_match = re.search(r'with\s+(.+?)(?:\s*\(\d+\))?$', title, re.IGNORECASE)
            if player_match:
                player = player_match.group(1).strip()
                episode = player
            else:
                episode = title.replace('_', ' ').strip()

            catalog = f"GG Millions {yr}"

            return CatalogTitles(
                content_type='full_episode',
                catalog_title=catalog,
                episode_title=episode
            )

        return CatalogTitles(
            content_type=content_type,
            catalog_title=f"GG Millions {year or ''}".strip(),
            episode_title=self._clean_for_episode(name)
        )

    def _generate_mpp(self, name: str, year: Optional[int], content_type: str) -> CatalogTitles:
        """Generate MPP catalog/episode titles"""

        # $5M GTD $5K MPP Main Event – Day 2
        match = re.match(r'^\$?[\d.]+[MK]?\s*GTD\s*\$?([\d.]+[MK]?)\s*(.+?)(?:\s*[-–]\s*(.+))?$', name, re.IGNORECASE)
        if match:
            buy_in = match.group(1)
            event = match.group(2).strip()
            session = match.group(3)

            catalog = f"MPP ${buy_in} {event}"
            episode = session.strip() if session else event

            return CatalogTitles(
                content_type='full_episode',
                catalog_title=catalog,
                episode_title=episode
            )

        return CatalogTitles(
            content_type=content_type,
            catalog_title=f"MPP {year or ''}".strip(),
            episode_title=self._clean_for_episode(name)
        )

    def _generate_hcl(self, name: str, year: Optional[int], content_type: str) -> CatalogTitles:
        """Generate HCL catalog/episode titles"""

        # HCL_2024_01_15_session1
        match = re.match(r'^HCL[_-]?(\d{4})[_-]?(\d{2})[_-]?(\d{2})[_-]?(.+)?', name, re.IGNORECASE)
        if match:
            yr = match.group(1)
            month = match.group(2)
            day = match.group(3)
            session = match.group(4) or ''

            catalog = f"Hustler Casino Live {yr}"
            episode = f"{month}/{day}"
            if session:
                episode += f" - {session.replace('_', ' ').strip()}"

            return CatalogTitles(
                content_type='full_episode',
                catalog_title=catalog,
                episode_title=episode
            )

        return CatalogTitles(
            content_type=content_type,
            catalog_title=f"Hustler Casino Live {year or ''}".strip(),
            episode_title=self._clean_for_episode(name)
        )

    def _generate_generic(
        self,
        name: str,
        project_code: str,
        year: Optional[int],
        content_type: str
    ) -> CatalogTitles:
        """Generate generic catalog/episode titles"""
        catalog = project_code
        if year:
            catalog = f"{project_code} {year}"

        episode = self._clean_for_episode(name)

        return CatalogTitles(
            content_type=content_type,
            catalog_title=catalog,
            episode_title=episode
        )

    def _extract_episode_from_folder_filename(self, filename: str) -> str:
        """
        Extract episode title from folder-style filename.

        Example:
            "1-wsop-2024-be-ev-01-5k-champions-reunion-ft-Conniff-hero-calls-with-A-high-chip-lead.mp4"
            → "FT - Conniff Hero Calls With A High Chip Lead"

            "33-wsop-2024-be-ev-58-50k-ppc-day4-negreanu-hits-straight-flush-scoops.mp4"
            → "Day 4 - Negreanu Hits Straight Flush Scoops"
        """
        # Remove extension
        name = re.sub(r'\.[a-zA-Z0-9]+$', '', filename)

        # Try to find episode marker and extract everything after it
        # Pattern: -ft-DESCRIPTION or -dayN-DESCRIPTION
        ft_match = re.search(r'-(ft)-(.+)$', name, re.IGNORECASE)
        if ft_match:
            marker = "Final Table"
            description = ft_match.group(2).replace('-', ' ').title()
            return f"{marker} - {description}"

        day_match = re.search(r'-(day\s*\d+)-(.+)$', name, re.IGNORECASE)
        if day_match:
            marker = day_match.group(1).replace('-', ' ').title()
            description = day_match.group(2).replace('-', ' ').title()
            return f"{marker} - {description}"

        # No episode marker found, try to extract from the end
        # For files like: 6-wsop-2024-be-ev-10-10k-omaha-hi-lo-championship
        # The event name itself becomes the "episode" (single video for this event)

        # Try to get event portion from folder pattern
        folder_match = re.match(
            r'^\d+-wsop-\d{4}-[a-z]+-ev-\d+-\d+k?-(.+)$',
            name,
            re.IGNORECASE
        )
        if folder_match:
            event_part = folder_match.group(1).replace('-', ' ').title()
            # If it looks like a complete event name, use "Video" or the event name
            return event_part if len(event_part) > 5 else "Video"

        # Fallback
        return "Video"

    def _parse_wsop_folder_event(self, text: str) -> Optional[dict]:
        """
        Parse WSOP folder-style event names into clean format.

        Examples:
            "6-wsop-2024-be-ev-10-10k-omaha-hi-lo-championship"
            → {"year": 2024, "event_name": "$10K Omaha Hi-Lo Championship"}

            "1-wsop-2024-be-ev-01-5k-champions-reunion-ft-Conniff-hero-calls.mp4"
            → {"year": 2024, "event_name": "$5K Champions Reunion"}

            "e-2021-10k-me"
            → {"year": 2021, "event_name": "$10K Main Event"}
        """
        if not text:
            return None

        # Try modern folder pattern with episode marker: N-wsop-YYYY-TYPE-ev-NN-BUYIN-EVENT-ft/day-...
        match = self.FOLDER_PATTERN.match(text)
        if match:
            year = int(match.group(2))
            buyin = match.group(5).upper()  # 10k → 10K
            event_raw = match.group(6)      # champions-reunion (stops at -ft-)

            # Format event name
            event_name = self._format_event_name(event_raw, buyin)

            return {
                'year': year,
                'event_name': event_name,
            }

        # Try full folder pattern (no episode marker)
        match_full = self.FOLDER_PATTERN_FULL.match(text)
        if match_full:
            year = int(match_full.group(2))
            buyin = match_full.group(5).upper()
            event_raw = match_full.group(6)

            event_name = self._format_event_name(event_raw, buyin)

            return {
                'year': year,
                'event_name': event_name,
            }

        # Try short Main Event pattern: N-wsop-YYYY-me
        me_match = self.ME_SHORT_PATTERN.match(text)
        if me_match:
            year = int(me_match.group(2))
            return {
                'year': year,
                'event_name': 'Main Event',
            }

        # Try legacy folder pattern: e-YYYY-BUYIN-EVENT
        legacy_match = self.LEGACY_FOLDER_PATTERN.match(text)
        if legacy_match:
            year = int(legacy_match.group(1))
            buyin = legacy_match.group(2).upper()
            event_raw = legacy_match.group(3)

            event_name = self._format_event_name(event_raw, buyin)

            return {
                'year': year,
                'event_name': event_name,
            }

        # Check if text contains folder-like patterns that should be cleaned
        # Example: "WSOP 2024 6-wsop-2024-be-ev-10-10k-omaha-hi-lo-championship"
        folder_in_text = re.search(r'(\d+-wsop-\d{4}-[a-z]+-ev-\d+-\d+k-.+)', text, re.IGNORECASE)
        if folder_in_text:
            return self._parse_wsop_folder_event(folder_in_text.group(1))

        legacy_in_text = re.search(r'(e-\d{4}-\d+k-.+)', text, re.IGNORECASE)
        if legacy_in_text:
            return self._parse_wsop_folder_event(legacy_in_text.group(1))

        return None

    def _format_event_name(self, event_raw: str, buyin: str) -> str:
        """
        Format raw event name into readable title.

        Examples:
            "omaha-hi-lo-championship", "10K" → "$10K Omaha Hi-Lo Championship"
            "nlh-shr", "250K" → "$250K NLH Super High Roller"
            "me", "10K" → "$10K Main Event"
        """
        # First check if entire string is a known variant (e.g., "nlh6max")
        event_lower = event_raw.lower()
        if event_lower in self.VARIANT_MAP:
            event_name = self.VARIANT_MAP[event_lower]
        else:
            # Split by hyphens
            parts = event_lower.split('-')

            # Map known variants
            formatted_parts = []
            for part in parts:
                if part in self.VARIANT_MAP:
                    formatted_parts.append(self.VARIANT_MAP[part])
                else:
                    # Title case for unknown parts
                    formatted_parts.append(part.title())

            # Join and clean
            event_name = ' '.join(formatted_parts)

        # Format buyin with dollar sign
        # Handle both "10K" and "1650" formats
        buyin_upper = buyin.upper()
        if buyin_upper.endswith('K'):
            formatted_buyin = f"${buyin_upper}"
        else:
            # Convert raw number to readable format (1650 → $1,650)
            try:
                amount = int(buyin)
                if amount >= 1000:
                    formatted_buyin = f"${amount:,}"
                else:
                    formatted_buyin = f"${amount}"
            except ValueError:
                formatted_buyin = f"${buyin}"

        return f"{formatted_buyin} {event_name}"

    def _extract_player_names(self, raw: str) -> str:
        """Extract player names from 'Player1 Cards vs Player2 Cards' format"""
        # Remove card notations (Ah, Kd, 9s, etc.)
        cleaned = re.sub(r'\s+[AKQJT2-9][hdcs][AKQJT2-9]?[hdcs]?', '', raw)
        cleaned = re.sub(r'\s+[2-9TJQKA][hdcs]', '', cleaned)

        # Clean up
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    def _extract_year(self, text: str) -> Optional[int]:
        """Extract year from text"""
        match = re.search(r'\b(19|20)\d{2}\b', text)
        if match:
            return int(match.group(0))
        return None

    def _clean_for_episode(self, name: str) -> str:
        """Clean filename for use as episode title"""
        clean = name

        # Remove file extension if present
        clean = re.sub(r'\.[a-zA-Z0-9]{2,4}$', '', clean)

        # Remove folder-style patterns that might be in the filename
        # e.g., "6-wsop-2024-be-ev-10-10k-omaha-hi-lo-championship" → ""
        clean = re.sub(r'\d+-wsop-\d{4}-[a-z]+-ev-\d+-\d+k-[a-z0-9-]+', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'e-\d{4}-\d+k-[a-z0-9-]+', '', clean, flags=re.IGNORECASE)

        # Remove common suffixes
        clean = re.sub(r'[_-]?(clean|nobug|nb|pgm|hires|stream|mastered|final_edit)$', '', clean, flags=re.IGNORECASE)

        # Remove duplicate WSOP references
        clean = re.sub(r'\bWSOP\s*\d{4}\s*', '', clean, flags=re.IGNORECASE)

        # Replace separators
        clean = re.sub(r'[-_]+', ' ', clean)

        # Clean up spaces
        clean = re.sub(r'\s+', ' ', clean).strip()

        # If nothing left, use a generic title
        if not clean or len(clean) < 3:
            clean = "Video"

        return clean


# Singleton instance
_catalog_title_generator = None


def get_catalog_title_generator() -> CatalogTitleGenerator:
    """Get CatalogTitleGenerator singleton"""
    global _catalog_title_generator
    if _catalog_title_generator is None:
        _catalog_title_generator = CatalogTitleGenerator()
    return _catalog_title_generator
