"""
Title Generator Service

Converts raw filenames into human-readable display titles.
"""
import re
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class TitleComponents:
    """Parsed title components"""
    project: str
    year: Optional[int] = None
    event_name: Optional[str] = None
    event_number: Optional[int] = None
    day: Optional[str] = None
    episode: Optional[int] = None
    description: Optional[str] = None
    version: Optional[str] = None


class TitleGenerator:
    """
    Generate readable display titles from video filenames.

    Examples:
        43-wsop-2024-me-day1b-Koury-set-JJs-vs-AQ-vs-AQ-CLEAN.mp4
        → WSOP 2024 Main Event Day1B - Koury Sets JJ vs AQ

        wsop-1999-me-nobug.mp4
        → WSOP 1999 Main Event

        WS12_Show_24_ME20_NB.mp4
        → WSOP 2012 Show #24 - ME Episode 20

        WP23-16.mp4
        → WSOP Paradise 2023 - Episode 16

        E01_GOG_final_edit_20231215.mp4
        → Game of Gold Episode 1
    """

    # Project code to display name
    PROJECT_NAMES = {
        'WSOP': 'WSOP',
        'HCL': 'Hustler Casino Live',
        'GGMILLIONS': 'GG Millions',
        'MPP': 'Mediterranean Poker Party',
        'PAD': 'Poker After Dark',
        'GOG': 'Game of Gold',
    }

    # Event type abbreviations
    EVENT_ABBREVS = {
        'me': 'Main Event',
        'be': 'Bracelet Event',
        'hr': 'High Roller',
        'shr': 'Super High Roller',
        'ft': 'Final Table',
    }

    # Game type display names
    GAME_NAMES = {
        'nlh': 'NLHE',
        'nlhe': 'NLHE',
        'plo': 'PLO',
        'plo8': 'PLO8',
        'mixed': 'Mixed',
    }

    # Version type display (optional suffix)
    VERSION_DISPLAY = {
        'clean': None,  # Don't show
        'mastered': None,
        'nobug': None,
        'generic': None,
        'stream': '[Stream]',
        'subclip': '[Clip]',
        'hires': '[HiRes]',
    }

    def generate(self, filename: str, project_code: str, year: Optional[int] = None) -> str:
        """
        Generate a display title from filename.

        Args:
            filename: Original filename (with or without extension)
            project_code: Project code (WSOP, HCL, etc.)
            year: Year (if known from folder/metadata)

        Returns:
            Human-readable display title
        """
        # Remove extension
        name = re.sub(r'\.[a-zA-Z0-9]+$', '', filename)

        # Parse based on project
        if project_code == 'WSOP':
            return self._generate_wsop(name, year)
        elif project_code == 'GOG':
            return self._generate_gog(name, year)
        elif project_code == 'PAD':
            return self._generate_pad(name, year)
        elif project_code == 'GGMILLIONS':
            return self._generate_ggmillions(name, year)
        elif project_code == 'MPP':
            return self._generate_mpp(name, year)
        elif project_code == 'HCL':
            return self._generate_hcl(name, year)
        else:
            return self._generate_generic(name, project_code, year)

    def _generate_wsop(self, name: str, year: Optional[int]) -> str:
        """Generate WSOP title"""
        parts = []

        # Pattern 1: New format (e.g., 43-wsop-2024-me-day1b-description)
        new_match = re.match(
            r'^(\d+)-wsop-(\d{4})-([a-z]+)-(?:ev-(\d+)-)?'
            r'(?:(\d+k?)-)?(?:([a-z]+)-)?(?:(day\d+[a-z]?|ft|hu)-)?(.+)?$',
            name.lower()
        )
        if new_match:
            ep_num = new_match.group(1)
            yr = new_match.group(2)
            event_type = new_match.group(3)
            event_num = new_match.group(4)
            buy_in = new_match.group(5)
            game = new_match.group(6)
            day = new_match.group(7)
            desc = new_match.group(8)

            parts.append(f"WSOP {yr}")

            # Event type
            if event_type in self.EVENT_ABBREVS:
                parts.append(self.EVENT_ABBREVS[event_type])
            elif event_num:
                parts.append(f"Event #{event_num}")

            # Day/Stage
            if day:
                day_display = day.upper().replace('DAY', 'Day ')
                parts.append(day_display)

            # Description (clean up)
            if desc:
                desc_clean = self._clean_description(desc)
                if desc_clean:
                    parts.append(f"- {desc_clean}")

            return ' '.join(parts)

        # Pattern 2: WS12_Show_24_ME20_NB (Show format)
        show_match = re.match(r'^WS(\d{2})_Show_(\d+)_?(.+)?', name, re.IGNORECASE)
        if show_match:
            yr = 2000 + int(show_match.group(1))
            show_num = show_match.group(2)
            extra = show_match.group(3) or ''

            parts.append(f"WSOP {yr} Show #{show_num}")

            # Parse ME episode if present
            me_match = re.search(r'ME(\d+)', extra, re.IGNORECASE)
            if me_match:
                parts.append(f"- ME Episode {me_match.group(1)}")

            return ' '.join(parts)

        # Pattern 3: WSOP_YEAR_EP (e.g., WSOP_2008_01)
        year_ep_match = re.match(r'^WSOP[_-](\d{4})[_-](\d+)', name, re.IGNORECASE)
        if year_ep_match:
            yr = year_ep_match.group(1)
            ep = year_ep_match.group(2)
            return f"WSOP {yr} - Episode {int(ep)}"

        # Pattern 4: WSOP13_ME21 (short format)
        short_match = re.match(r'^WSOP(\d{2})[_-]?(ME)?(\d+)', name, re.IGNORECASE)
        if short_match:
            yr = 2000 + int(short_match.group(1))
            is_me = short_match.group(2)
            ep = short_match.group(3)

            if is_me:
                return f"WSOP {yr} Main Event - Episode {int(ep)}"
            return f"WSOP {yr} - Episode {int(ep)}"

        # Pattern 5: WP23-16 (Paradise format)
        paradise_match = re.match(r'^WP(\d{2})-(\d+)', name, re.IGNORECASE)
        if paradise_match:
            yr = 2000 + int(paradise_match.group(1))
            ep = paradise_match.group(2)
            return f"WSOP Paradise {yr} - Episode {int(ep)}"

        # Pattern 6: WCLA24-15 (Circuit format)
        circuit_match = re.match(r'^W([A-Z]{2,4})(\d{2})-(\d+)', name, re.IGNORECASE)
        if circuit_match:
            location = circuit_match.group(1).upper()
            yr = 2000 + int(circuit_match.group(2))
            ep = circuit_match.group(3)

            loc_names = {'CLA': 'Circuit LA', 'E': 'Europe'}
            loc_display = loc_names.get(location, f"Circuit {location}")
            return f"WSOP {loc_display} {yr} - Episode {int(ep)}"

        # Pattern 7: wsop-1999-me-nobug (archive format)
        archive_match = re.match(r'^wsop[_-](\d{4})[_-]?(me)?', name, re.IGNORECASE)
        if archive_match:
            yr = archive_match.group(1)
            is_me = archive_match.group(2)
            if is_me:
                return f"WSOP {yr} Main Event"
            return f"WSOP {yr}"

        # Fallback: Use year if available
        if year:
            return f"WSOP {year} - {self._clean_description(name)}"

        return f"WSOP - {self._clean_description(name)}"

    def _generate_gog(self, name: str, year: Optional[int]) -> str:
        """Generate Game of Gold title"""
        # E01_GOG_final_edit_20231215
        match = re.match(r'^E(\d+)_GOG', name, re.IGNORECASE)
        if match:
            ep = int(match.group(1))
            return f"Game of Gold Episode {ep}"

        return f"Game of Gold - {self._clean_description(name)}"

    def _generate_pad(self, name: str, year: Optional[int]) -> str:
        """Generate Poker After Dark title"""
        # PAD S12 E01
        match = re.match(r'^PAD[\s_-]*S(\d+)[\s_-]*E(\d+)', name, re.IGNORECASE)
        if match:
            season = int(match.group(1))
            ep = int(match.group(2))
            return f"Poker After Dark S{season} E{ep}"

        return f"Poker After Dark - {self._clean_description(name)}"

    def _generate_ggmillions(self, name: str, year: Optional[int]) -> str:
        """Generate GG Millions title"""
        # 250507_Super High Roller Poker FINAL TABLE with Joey Ingram
        match = re.match(r'^(\d{6})_(.+)', name)
        if match:
            date_str = match.group(1)
            title = match.group(2)

            # Parse date
            yr = 2000 + int(date_str[:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])

            # Clean title
            title_clean = title.replace('_', ' ')
            # Remove common suffixes
            title_clean = re.sub(r'\s*FINAL\s*TABLE\s*', ' Final Table ', title_clean, flags=re.IGNORECASE)
            title_clean = re.sub(r'\s*with\s+', ' - ', title_clean, flags=re.IGNORECASE)
            title_clean = re.sub(r'\s+', ' ', title_clean).strip()

            return f"GG Millions {yr}/{month:02d}/{day:02d} {title_clean}"

        return f"GG Millions - {self._clean_description(name)}"

    def _generate_mpp(self, name: str, year: Optional[int]) -> str:
        """Generate MPP title"""
        # $1M GTD $1K Mystery Bounty
        match = re.match(r'^\$?([\d.]+[MK]?)\s*GTD\s*\$?([\d.]+[MK]?)\s*(.+)', name, re.IGNORECASE)
        if match:
            gtd = match.group(1)
            buy_in = match.group(2)
            event = match.group(3).strip()
            return f"MPP ${buy_in} {event} (${gtd} GTD)"

        return f"Mediterranean Poker Party - {self._clean_description(name)}"

    def _generate_hcl(self, name: str, year: Optional[int]) -> str:
        """Generate HCL title"""
        # HCL_2024_01_15_session1
        match = re.match(r'^HCL[_-]?(\d{4})[_-]?(\d{2})[_-]?(\d{2})[_-]?(.+)?', name, re.IGNORECASE)
        if match:
            yr = match.group(1)
            month = match.group(2)
            day = match.group(3)
            session = match.group(4) or ''

            title = f"Hustler Casino Live {yr}/{month}/{day}"
            if session:
                title += f" - {self._clean_description(session)}"
            return title

        return f"Hustler Casino Live - {self._clean_description(name)}"

    def _generate_generic(self, name: str, project_code: str, year: Optional[int]) -> str:
        """Generate generic title"""
        project_name = self.PROJECT_NAMES.get(project_code, project_code)
        clean_name = self._clean_description(name)

        if year:
            return f"{project_name} {year} - {clean_name}"
        return f"{project_name} - {clean_name}"

    def _clean_description(self, desc: str) -> str:
        """Clean up description text"""
        if not desc:
            return ""

        # Replace separators with spaces
        clean = re.sub(r'[-_]+', ' ', desc)

        # Remove version suffixes
        clean = re.sub(r'\b(clean|nobug|nb|pgm|hires)\b', '', clean, flags=re.IGNORECASE)

        # Capitalize words
        words = clean.split()
        capitalized = []
        for word in words:
            if word.upper() in ('VS', 'AND', 'OR', 'THE', 'A', 'AN', 'OF', 'IN', 'ON', 'AT', 'TO', 'FOR'):
                capitalized.append(word.lower())
            elif re.match(r'^[A-Z]{2,}$', word):  # All caps abbreviation
                capitalized.append(word)
            else:
                capitalized.append(word.capitalize())

        result = ' '.join(capitalized).strip()

        # Clean up multiple spaces
        result = re.sub(r'\s+', ' ', result)

        return result


# Singleton instance
_title_generator = None


def get_title_generator() -> TitleGenerator:
    """Get TitleGenerator singleton"""
    global _title_generator
    if _title_generator is None:
        _title_generator = TitleGenerator()
    return _title_generator
