# LLD 03: File Parser Design

> **버전**: 1.2.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09 | **수정일**: 2025-12-09

---

## 1. 개요

7개 프로젝트별 파일명 패턴을 파싱하여 메타데이터를 추출하는 시스템.

### 1.1 파서 구조

```
ParserFactory
    │
    ├── WSOPBraceletParser
    ├── WSOPCircuitParser
    ├── GGMillionsParser
    ├── GOGParser
    ├── PADParser
    ├── MPPParser
    └── GenericParser (fallback)
```

---

## 2. 프로젝트별 파서

### 2.1 WSOP Bracelet Parser

**패턴**: `{번호}-wsop-{연도}-be-ev-{이벤트}-{바이인}-{게임}-{추가정보}.mp4`

```python
class WSOPBraceletParser(BaseParser):
    PATTERN = re.compile(
        r'^(\d+)-wsop-(\d{4})-be-ev-(\d+)-(\d+k?)-([a-z0-9]+)-'
        r'(hr-)?([a-z]+)-(.+)\.(mp4|mov|mxf)$',
        re.IGNORECASE
    )

    def parse(self, filename: str) -> ParsedFile:
        match = self.PATTERN.match(filename)
        if not match:
            return None

        return ParsedFile(
            clip_number=int(match.group(1)),
            year=int(match.group(2)),
            event_number=int(match.group(3)),
            buy_in=self._parse_buy_in(match.group(4)),
            game_type=self._normalize_game(match.group(5)),
            is_high_roller=bool(match.group(6)),
            table_type=match.group(7),
            title=match.group(8).replace('-', ' '),
            extension=match.group(9)
        )
```

**예시**:
| 파일명 | 추출 결과 |
|--------|----------|
| `10-wsop-2024-be-ev-21-25k-nlh-hr-ft-title.mp4` | year=2024, ev=21, buy_in=25000, game=NLHE, table=ft |

---

### 2.2 WSOP Circuit Parser

**패턴**: `WCLA{연도}-{번호}.mp4` 또는 `{이벤트명}_Day{N}.mp4`

```python
class WSOPCircuitParser(BaseParser):
    PATTERNS = [
        re.compile(r'^WCLA(\d{2})-(\d+)\.(mp4|mov)$'),
        re.compile(r'^(.+)_Day(\d+)\.(mp4|mov)$'),
    ]

    def parse(self, filename: str) -> ParsedFile:
        for pattern in self.PATTERNS:
            match = pattern.match(filename)
            if match:
                return self._extract(match, pattern)
        return None
```

---

### 2.3 GGMillions Parser

**패턴**: `{YYMMDD}_Super High Roller...with {플레이어}.mp4`

> **⚠️ 주의**: 파일명에 공백, 특수문자가 포함될 수 있음. 유연한 패턴 필요.

```python
class GGMillionsParser(BaseParser):
    """
    GGMillions 파일명 파서

    지원 패턴:
    - 250507_Super High Roller Poker FINAL TABLE with Joey Ingram.mp4
    - 250507_Super High Roller with Phil Ivey.mp4 (축약형)
    - 250507_GGMillions_FT_Joey_Ingram.mp4 (대안 형식)
    """

    PATTERNS = [
        # 정규 형식: 날짜_Super High Roller Poker FINAL TABLE with 플레이어.ext
        re.compile(
            r'^(\d{6})_Super High Roller Poker FINAL TABLE with (.+)\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
        # 축약 형식: 날짜_Super High Roller with 플레이어.ext
        re.compile(
            r'^(\d{6})_Super High Roller with (.+)\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
        # 대안 형식: 날짜_GGMillions_FT_플레이어.ext
        re.compile(
            r'^(\d{6})_GGMillions_FT_(.+)\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
    ]

    def parse(self, filename: str) -> ParsedFile:
        for pattern in self.PATTERNS:
            match = pattern.match(filename)
            if match:
                return self._extract(match)
        return None

    def _extract(self, match) -> ParsedFile:
        date_str = match.group(1)
        featured_player = match.group(2).replace('_', ' ').strip()

        return ParsedFile(
            date=datetime.strptime(date_str, '%y%m%d'),
            event_type='super_high_roller',
            table_type='final_table',
            featured_player=featured_player,
            extension=match.group(3).lower()
        )
```

---

### 2.4 GOG Parser

**패턴**: `E{번호}_GOG_final_edit_{클린본?}_{날짜}.mp4`

> **⚠️ 주의**: 에피소드 번호 자릿수, 한글 버전명 처리

```python
class GOGParser(BaseParser):
    """
    GOG 시리즈 파일명 파서

    지원 패턴:
    - E01_GOG_final_edit_20231215.mp4
    - E01_GOG_final_edit_클린본_20231215.mp4
    - E1_GOG_final_20231215.mp4 (자릿수 유연)
    - GOG_EP01_clean_20231215.mp4 (대안 형식)
    """

    PATTERNS = [
        # 정규 형식: E번호_GOG_final_edit_[클린본_]날짜.ext
        re.compile(
            r'^E(\d{1,3})_GOG_final_edit_(클린본_)?(\d{8})\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
        # 축약 형식: E번호_GOG_final_날짜.ext
        re.compile(
            r'^E(\d{1,3})_GOG_final_(\d{8})\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
        # 대안 형식: GOG_EP번호_[버전]_날짜.ext
        re.compile(
            r'^GOG_EP(\d{1,3})_(clean|final)?_?(\d{8})\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
    ]

    def parse(self, filename: str) -> ParsedFile:
        for idx, pattern in enumerate(self.PATTERNS):
            match = pattern.match(filename)
            if match:
                return self._extract(match, idx)
        return None

    def _extract(self, match, pattern_idx: int) -> ParsedFile:
        episode_number = int(match.group(1))

        # 버전 타입 결정
        if pattern_idx == 0:  # 정규 형식
            version_type = 'clean' if match.group(2) else 'final_edit'
            date_str = match.group(3)
            ext = match.group(4)
        elif pattern_idx == 1:  # 축약 형식
            version_type = 'final_edit'
            date_str = match.group(2)
            ext = match.group(3)
        else:  # 대안 형식
            version_type = match.group(2).lower() if match.group(2) else 'final_edit'
            date_str = match.group(3)
            ext = match.group(4)

        return ParsedFile(
            episode_number=episode_number,
            version_type=version_type,
            date=datetime.strptime(date_str, '%Y%m%d'),
            extension=ext.lower()
        )
```

---

### 2.5 PAD Parser

**패턴**: `PAD S{시즌} E{에피소드}.mp4`

> **⚠️ 주의**: 구분자 유연성 (공백, 언더스코어, 하이픈)

```python
class PADParser(BaseParser):
    """
    Poker After Dark 파일명 파서

    지원 패턴:
    - PAD S12 E01.mp4
    - PAD_S12_E01.mp4
    - PAD-S12-E01.mp4
    - Poker_After_Dark_S12_E01.mp4
    """

    PATTERNS = [
        # 정규 형식: PAD S시즌 E에피소드.ext (공백 구분)
        re.compile(
            r'^PAD[\s_-]+S(\d+)[\s_-]+E(\d+)\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
        # 전체 이름: Poker After Dark S시즌 E에피소드.ext
        re.compile(
            r'^Poker[\s_]+After[\s_]+Dark[\s_]+S(\d+)[\s_]+E(\d+)\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
        # 축약형: PAD_시즌에피소드.ext (예: PAD_1201.mp4)
        re.compile(
            r'^PAD[\s_-]+(\d{2})(\d{2})\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
    ]

    def parse(self, filename: str) -> ParsedFile:
        for idx, pattern in enumerate(self.PATTERNS):
            match = pattern.match(filename)
            if match:
                return self._extract(match, idx)
        return None

    def _extract(self, match, pattern_idx: int) -> ParsedFile:
        if pattern_idx <= 1:  # 정규/전체 형식
            season = int(match.group(1))
            episode = int(match.group(2))
            ext = match.group(3)
        else:  # 축약형
            season = int(match.group(1))
            episode = int(match.group(2))
            ext = match.group(3)

        return ParsedFile(
            season_number=season,
            episode_number=episode,
            event_type='tv_series',
            extension=ext.lower()
        )
```

---

### 2.6 HCL Parser (신규)

**패턴**: `HCL {연도} Episode {번호} Part {번호}.mp4` 또는 `Hustler Casino Live {연도}.mp4`

> **참고**: Hustler Casino Live 스트리밍 포커 쇼. 에피소드/파트 구조.

```python
class HCLParser(BaseParser):
    """
    Hustler Casino Live 파일명 파서

    지원 패턴:
    - HCL 2024 Episode 15 Part 2.mp4
    - Hustler Casino Live 2023 Poker Game.mp4
    - HCL Season 3 Episode 10.mp4
    - HCL_2024_BigGame_Part1.mp4
    - HCL_2024-03-15_High_Stakes.mp4 (날짜 형식)
    """

    PATTERNS = [
        # 정규 형식: HCL 연도 Episode 번호 Part 번호.ext
        re.compile(
            r'^(?:HCL|Hustler\s*Casino\s*Live)\s*'
            r'(?P<year>\d{4})?\s*'
            r'(?:Season\s*(?P<season>\d+))?\s*'
            r'(?:Ep(?:isode)?\s*(?P<episode>\d+))?\s*'
            r'(?P<event_name>[^-_.]+?)?\s*'
            r'(?:Part\s*(?P<part>\d+))?\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
        # 날짜 형식: HCL_YYYY-MM-DD_제목.ext
        re.compile(
            r'^HCL[_\s]+(\d{4})-(\d{2})-(\d{2})[_\s]+(.+)\.(mp4|mov|mxf)$',
            re.IGNORECASE
        ),
    ]

    def parse(self, filename: str) -> ParsedFile:
        for idx, pattern in enumerate(self.PATTERNS):
            match = pattern.match(filename)
            if match:
                return self._extract(match, idx)
        return None

    def _extract(self, match, pattern_idx: int) -> ParsedFile:
        if pattern_idx == 0:  # 정규 형식
            groups = match.groupdict()
            return ParsedFile(
                year=int(groups['year']) if groups.get('year') else None,
                season_number=int(groups['season']) if groups.get('season') else None,
                episode_number=int(groups['episode']) if groups.get('episode') else None,
                event_name=groups.get('event_name', '').strip() if groups.get('event_name') else None,
                part=int(groups['part']) if groups.get('part') else None,
                event_type='live_stream',
            )
        else:  # 날짜 형식
            return ParsedFile(
                date=datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))),
                event_name=match.group(4).replace('_', ' '),
                event_type='live_stream',
            )
```

**예시**:
| 파일명 | 추출 결과 |
|--------|----------|
| `HCL 2024 Episode 15 Part 2.mp4` | year=2024, episode=15, part=2 |
| `Hustler Casino Live 2023 High Stakes.mp4` | year=2023, event_name="High Stakes" |
| `HCL_2024-03-15_Phil_Ivey.mp4` | date=2024-03-15, event_name="Phil Ivey" |

---

### 2.7 MPP Parser

**패턴**: `${GTD} GTD ${바이인} {이벤트타입}.mp4`

```python
class MPPParser(BaseParser):
    PATTERN = re.compile(
        r'^\$(\d+)([MK])? GTD\s+\$(\d+)([MK])?\s+(.+)\.(mp4|mov)$'
    )

    def parse(self, filename: str) -> ParsedFile:
        match = self.PATTERN.match(filename)
        if not match:
            return None

        return ParsedFile(
            gtd_amount=self._parse_money(match.group(1), match.group(2)),
            buy_in=self._parse_money(match.group(3), match.group(4)),
            event_name=match.group(5),
            extension=match.group(6)
        )
```

---

## 3. Parser Factory

```python
class ParserFactory:
    PARSERS = {
        'WSOP': [WSOPBraceletParser, WSOPCircuitParser],
        'GGMILLIONS': [GGMillionsParser],
        'GOG': [GOGParser],
        'PAD': [PADParser],
        'MPP': [MPPParser],
    }

    @classmethod
    def parse(cls, filename: str, project_code: str) -> ParsedFile:
        parsers = cls.PARSERS.get(project_code, [GenericParser])

        for parser_cls in parsers:
            parser = parser_cls()
            result = parser.parse(filename)
            if result:
                result.project_code = project_code
                return result

        # Fallback
        return GenericParser().parse(filename)
```

---

## 4. 버전 타입 감지

폴더 경로에서 버전 타입 추출:

```python
VERSION_PATTERNS = {
    'Clean': 'clean',
    'Mastered': 'mastered',
    'STREAM': 'stream',
    'SUBCLIP': 'subclip',
    'Generics': 'generic',
    'HiRes': 'hires',
}

def detect_version_type(file_path: str) -> str:
    for pattern, version in VERSION_PATTERNS.items():
        if pattern in file_path:
            return version

    # 파일명에서 감지
    if '클린본' in file_path or '-clean' in file_path.lower():
        return 'clean'
    if 'final_edit' in file_path.lower():
        return 'final_edit'
    if '-nobug' in file_path.lower():
        return 'nobug'

    return None
```

---

## 5. 게임 타입 정규화

```python
GAME_TYPE_MAP = {
    'nlh': 'NLHE',
    'nlhe': 'NLHE',
    'plo': 'PLO',
    'plo8': 'PLO8',
    'mixed': 'Mixed',
    'horse': 'HORSE',
    'stud': 'Stud',
    'razz': 'Razz',
    '27td': '2-7TD',
    '27sd': '2-7SD',
}

def normalize_game_type(raw: str) -> str:
    return GAME_TYPE_MAP.get(raw.lower(), raw.upper())
```

---

## 6. 테스트 케이스

```python
@pytest.mark.parametrize("filename,expected", [
    (
        "10-wsop-2024-be-ev-21-25k-nlh-hr-ft-title.mp4",
        {"year": 2024, "event_number": 21, "buy_in": 25000, "game_type": "NLHE"}
    ),
    (
        "WCLA24-15.mp4",
        {"year": 2024, "clip_number": 15}
    ),
    (
        "250507_Super High Roller Poker FINAL TABLE with Joey Ingram.mp4",
        {"date": "2025-05-07", "featured_player": "Joey Ingram"}
    ),
    (
        "E01_GOG_final_edit_클린본_20231215.mp4",
        {"episode_number": 1, "version_type": "clean"}
    ),
])
def test_parsers(filename, expected):
    result = ParserFactory.parse(filename, detect_project(filename))
    for key, value in expected.items():
        assert getattr(result, key) == value
```

---

## 7. 파일 필터

동기화 과정에서 비-MP4 파일, macOS 메타데이터 파일, 중복 파일을 식별하여 DB에 마킹합니다.

### 7.1 FileFilter 클래스

```python
@dataclass
class FilterResult:
    """파일 필터 결과"""
    file_path: str
    is_hidden: bool = False
    hidden_reason: Optional[str] = None

class FileFilter:
    """
    동기화 전 파일 필터링.
    삭제하지 않고 DB에 숨김 상태로 마킹.
    """

    # 허용 확장자 (mp4만)
    ALLOWED_EXTENSIONS = {'.mp4'}

    # 제외 패턴 (macOS 메타데이터)
    EXCLUDE_PATTERNS = [
        re.compile(r'^\._'),           # macOS resource fork
        re.compile(r'^\.DS_Store$'),   # macOS folder metadata
        re.compile(r'^Thumbs\.db$'),   # Windows thumbnail cache
    ]

    def check_file(self, file_path: str) -> FilterResult:
        """파일 필터링 체크"""
        filename = Path(file_path).name
        ext = Path(file_path).suffix.lower()

        # macOS 메타데이터 체크
        for pattern in self.EXCLUDE_PATTERNS:
            if pattern.match(filename):
                return FilterResult(file_path, True, 'macos_meta')

        # 확장자 체크
        if ext not in self.ALLOWED_EXTENSIONS:
            return FilterResult(file_path, True, 'non_mp4')

        return FilterResult(file_path, False, None)
```

### 7.2 숨김 사유 (hidden_reason)

| 값 | 설명 | 예시 |
|----|------|------|
| `macos_meta` | macOS 리소스 포크, 메타데이터 | `._video.mp4`, `.DS_Store` |
| `non_mp4` | MP4 외 확장자 | `.mxf`, `.mov`, `.avi`, `.mkv` |
| `duplicate` | 중복 파일 (동일 크기 + 유사 이름) | 백업 복사본 |

### 7.3 DB 스키마

```sql
-- video_files 테이블 필터링 컬럼
ALTER TABLE pokervod.video_files
ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT false;

ALTER TABLE pokervod.video_files
ADD COLUMN IF NOT EXISTS hidden_reason VARCHAR(50);

-- 활성 파일 조회 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_video_files_hidden
ON pokervod.video_files(is_hidden)
WHERE is_hidden = false;
```

### 7.4 중복 탐지 (pg_trgm)

동일 파일 크기 + 파일명 유사도 80% 이상을 중복으로 판단:

```sql
-- pg_trgm 확장 설치
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 중복 파일 마킹 쿼리
WITH duplicates AS (
    SELECT
        v1.id,
        v1.file_name,
        v2.file_name as original_name,
        similarity(v1.file_name, v2.file_name) as sim
    FROM pokervod.video_files v1
    JOIN pokervod.video_files v2
        ON v1.file_size_bytes = v2.file_size_bytes
        AND v1.id > v2.id
    WHERE similarity(v1.file_name, v2.file_name) > 0.8
)
UPDATE pokervod.video_files
SET is_hidden = true, hidden_reason = 'duplicate'
WHERE id IN (SELECT id FROM duplicates);
```

### 7.5 통합 흐름

```
NAS 파일 스캔
    ↓
FileFilter.check_file()
    ↓
┌─────────────────────────┐
│ is_hidden=true?         │
│   → episode_id = NULL   │
│   → 카탈로그 제외       │
│                         │
│ is_hidden=false?        │
│   → 정상 처리           │
│   → 에피소드 연결       │
└─────────────────────────┘
    ↓
DB 저장 (모든 파일 추적)
```

### 7.6 카탈로그 조회 (숨김 파일 제외)

```sql
-- 활성 비디오 파일만 조회
SELECT * FROM pokervod.video_files
WHERE is_hidden = false;

-- 숨김 파일 통계
SELECT hidden_reason, COUNT(*)
FROM pokervod.video_files
WHERE is_hidden = true
GROUP BY hidden_reason;
```

---

## 8. 참조

| 문서 | 설명 |
|------|------|
| [02_SYNC_SYSTEM.md](./02_SYNC_SYSTEM.md) | 동기화 시스템 |
| [NAS_FOLDER_STRUCTURE.md](../NAS_FOLDER_STRUCTURE.md) | NAS 폴더 구조 |

---

**문서 버전**: 1.2.0
**작성일**: 2025-12-09
**수정일**: 2025-12-09
**상태**: Updated - File filter added

### 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.2.0 | 2025-12-09 | 파일 필터 섹션 추가 - macOS 메타파일, 비-MP4, 중복 파일 마킹 |
| 1.1.0 | 2025-12-09 | #9 GGMillions/PAD/GOG 파서 정규식 개선 - 다중 패턴 지원, IGNORECASE, 유연한 구분자 |
| 1.0.0 | 2025-12-09 | 초기 버전 |
