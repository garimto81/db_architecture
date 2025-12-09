# LLD 03: File Parser Design

> **버전**: 1.0.0 | **기준 PRD**: v5.1 | **작성일**: 2025-12-09

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

```python
class GGMillionsParser(BaseParser):
    PATTERN = re.compile(
        r'^(\d{6})_Super High Roller Poker FINAL TABLE with (.+)\.(mp4|mov)$'
    )

    def parse(self, filename: str) -> ParsedFile:
        match = self.PATTERN.match(filename)
        if not match:
            return None

        date_str = match.group(1)
        return ParsedFile(
            date=datetime.strptime(date_str, '%y%m%d'),
            event_type='super_high_roller',
            table_type='final_table',
            featured_player=match.group(2),
            extension=match.group(3)
        )
```

---

### 2.4 GOG Parser

**패턴**: `E{번호}_GOG_final_edit_{클린본?}_{날짜}.mp4`

```python
class GOGParser(BaseParser):
    PATTERN = re.compile(
        r'^E(\d{2})_GOG_final_edit_(클린본_)?(\d{8})\.(mp4|mov)$'
    )

    def parse(self, filename: str) -> ParsedFile:
        match = self.PATTERN.match(filename)
        if not match:
            return None

        return ParsedFile(
            episode_number=int(match.group(1)),
            version_type='clean' if match.group(2) else 'final_edit',
            date=datetime.strptime(match.group(3), '%Y%m%d'),
            extension=match.group(4)
        )
```

---

### 2.5 PAD Parser

**패턴**: `PAD S{시즌} E{에피소드}.mp4`

```python
class PADParser(BaseParser):
    PATTERN = re.compile(r'^PAD S(\d+) E(\d+)\.(mp4|mov)$')

    def parse(self, filename: str) -> ParsedFile:
        match = self.PATTERN.match(filename)
        if not match:
            return None

        return ParsedFile(
            season_number=int(match.group(1)),
            episode_number=int(match.group(2)),
            event_type='tv_series',
            extension=match.group(3)
        )
```

---

### 2.6 MPP Parser

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

## 7. 참조

| 문서 | 설명 |
|------|------|
| [02_SYNC_SYSTEM.md](./02_SYNC_SYSTEM.md) | 동기화 시스템 |
| [NAS_FOLDER_STRUCTURE.md](../NAS_FOLDER_STRUCTURE.md) | NAS 폴더 구조 |

---

**문서 버전**: 1.0.0
**작성일**: 2025-12-09
