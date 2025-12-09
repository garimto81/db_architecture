# NAS 폴더 구조 상세 분석
## GGP NAS ARCHIVE 폴더 구조 (v1.0)

**NAS 경로**: `\\10.10.100.122\docker\GGPNAs\ARCHIVE`
**분석일**: 2025-12-09

---

## 1. 전체 폴더 구조 개요

```
ARCHIVE/
├── GGMillions/           # Super High Roller Poker 파이널 테이블
├── GOG 최종/             # GOG 시리즈 (12 에피소드)
├── HCL/                  # Hustler Casino Live
├── MPP/                  # Mediterranean Poker Party
├── PAD/                  # Poker After Dark
└── WSOP/                 # World Series of Poker
```

---

## 2. 프로젝트별 상세 구조

### 2.1 GGMillions (13 파일)

```
GGMillions/
├── 250507_Super High Roller Poker FINAL TABLE with Joey ingram.mp4
├── 250514_Super High Roller Poker FINAL TABLE with Fedor Holz.mp4
├── 250521_Super High Roller Poker FINAL TABLE with Xuan Liu.mp4
├── 250604_Super High Roller Poker FINAL TABLE with Denys Chufarin.mp4
├── 250611_Super High Roller Poker FINAL TABLE with Rayan Chamas.mp4
├── 250618_Super High Roller Poker FINAL TABLE with Kevin Martin & Dan Cates.mp4
├── Super High Roller Poker FINAL TABLE with Benjamin Rolle (1).mp4
├── Super High Roller Poker FINAL TABLE with Frank Brannan.mp4
├── Super High Roller Poker FINAL TABLE with Kevin Rabichow.mp4
├── Super High Roller Poker FINAL TABLE with Michael Jozoff & Michael Berk.mp4
├── Super High Roller Poker FINAL TABLE with Michael Mizrachi.mp4
├── Super High Roller Poker FINAL TABLE with Paulius Vaitiekunas.mp4
└── Super High Roller Poker FINAL TABLE with Robert Mizrachi (1).mp4
```

**파일명 패턴**:
- 패턴 A: `{YYMMDD}_Super High Roller Poker FINAL TABLE with {플레이어}.mp4`
- 패턴 B: `Super High Roller Poker FINAL TABLE with {플레이어}.mp4`

**추출 가능 메타데이터**:
| 필드 | 설명 | 예시 |
|------|------|------|
| date | 방송일 (YYMMDD) | 250507 → 2025-05-07 |
| featured_player | 주요 출연 플레이어 | Joey Ingram, Fedor Holz |

---

### 2.2 GOG 최종 (12 에피소드)

```
GOG 최종/
├── e01/
│   ├── E01_GOG_final_edit_231106.mp4
│   └── E01_GOG_final_edit_클린본.mp4
├── e02/
│   ├── E02_GOG_final_edit_20231113_수정.mp4
│   └── E02_GOG_final_edit_클린본_20231031.mp4
├── e03/
│   ├── E03_GOG_final_edit_20231113.mp4
│   └── E03_GOG_final_edit_클린본_20231110.mp4
├── e04/ ~ e12/
│   └── ... (동일 구조)
└── e03 - 바로 가기.lnk
```

**파일명 패턴**:
- Final Edit: `E{번호}_GOG_final_edit_{YYYYMMDD}[_수정].mp4`
- Clean: `E{번호}_GOG_final_edit_클린본_{YYYYMMDD}.mp4`

**추출 가능 메타데이터**:
| 필드 | 설명 | 예시 |
|------|------|------|
| episode_number | 에피소드 번호 | E01, E02, ... E12 |
| version_type | 버전 타입 | final_edit, 클린본 |
| edit_date | 편집일 | 231106, 20231113 |

---

### 2.3 HCL (Hustler Casino Live)

```
HCL/
├── HCL Poker Clip/
│   ├── 2023/     # (현재 비어있음)
│   ├── 2024/     # (현재 비어있음)
│   └── 2025/     # (현재 비어있음)
└── SHOW, SERIES/ # (현재 비어있음)
```

**상태**: 폴더 구조만 존재, 파일 없음 (향후 업로드 예정)

---

### 2.4 MPP (Mediterranean Poker Party)

```
MPP/
└── 2025 MPP Cyprus/
    ├── $1M GTD   $1K PokerOK Mystery Bounty/
    │   ├── $1M GTD   $1K PokerOK Mystery Bounty ? Day 1A.mp4
    │   ├── $1M GTD   $1K PokerOK Mystery Bounty ? Day 1C.mp4
    │   ├── $1M GTD   $1K PokerOK Mystery Bounty ? Final Day.mp4
    │   └── $1M GTD   $1K PokerOK Mystery Bounty ? Final Table.mp4
    │
    ├── $2M GTD   $2K Luxon Pay Grand Final/
    │   ├── $2M GTD   $2K Luxon Pay Grand Final ? Day 1C.mp4
    │   ├── $2M GTD   $2K Luxon Pay Grand Final ? Day 2.mp4
    │   └── $2M GTD   $2K Luxon Pay Grand Final ? Final Table.mp4
    │
    └── $5M GTD   $5K MPP Main Event/
        ├── $5M GTD   $5K MPP Main Event ? Day 2.mp4
        ├── $5M GTD   $5K MPP Main Event ? Day 3 Session 1.mp4
        ├── $5M GTD   $5K MPP Main Event ? Day 3 Session 2.mp4
        └── $5M GTD   $5K MPP Main Event ? Final Day.mp4
```

**파일명 패턴**: `${GTD금액} GTD   ${바이인} {이벤트명} ? {Day/Final}.mp4`

**추출 가능 메타데이터**:
| 필드 | 설명 | 예시 |
|------|------|------|
| gtd_amount | 보장 상금 | $1M, $2M, $5M |
| buy_in | 바이인 | $1K, $2K, $5K |
| event_name | 이벤트명 | Mystery Bounty, Main Event |
| day | 진행일 | Day 1A, Day 2, Final Day |
| location | 장소 | Cyprus |
| year | 연도 | 2025 |

---

### 2.5 PAD (Poker After Dark)

```
PAD/
├── PAD S12/          # 시즌 12 (21 에피소드)
│   ├── pad-s12-ep01-002.mp4
│   ├── pad-s12-ep02-003.mp4
│   ├── ...
│   └── pad-s12-ep21-019.mp4
│
└── PAD S13/          # 시즌 13 (23 에피소드)
    ├── PAD_S13_EP01_GGPoker-001.mp4
    ├── PAD_S13_EP02_GGPoker-002.mp4
    ├── ...
    ├── PAD_S13_EP16_FinalLook_HiRes-021.mp4
    ├── ...
    └── PAD_S13_EP23_BestOf_FinalLook-HiRes-019.mp4
```

**파일명 패턴**:
- S12: `pad-s12-ep{번호}-{코드}.mp4`
- S13: `PAD_S13_EP{번호}_{버전}-{코드}.mp4`

**추출 가능 메타데이터**:
| 필드 | 설명 | 예시 |
|------|------|------|
| season | 시즌 번호 | S12, S13 |
| episode | 에피소드 번호 | EP01 ~ EP23 |
| version | 버전 | GGPoker, FinalLook_HiRes |
| internal_code | 내부 코드 | 001, 002, 021 |

---

### 2.6 WSOP (World Series of Poker)

#### 2.6.1 전체 구조

```
WSOP/
├── WSOP ARCHIVE (PRE-2016)/    # 역사 아카이브 (1973-2016)
├── WSOP Bracelet Event/         # 브레이슬릿 이벤트
│   ├── WSOP-EUROPE/
│   ├── WSOP-LAS VEGAS/
│   └── WSOP-PARADISE/
└── WSOP Circuit Event/          # 서킷 이벤트
    ├── WSOP Super Ciruit/
    └── WSOP-Circuit/
```

---

#### 2.6.2 WSOP ARCHIVE (PRE-2016)

```
WSOP ARCHIVE (PRE-2016)/
├── WSOP 1973/
│   ├── WSOP - 1973.avi
│   ├── WSOP - 1973.mp4
│   └── wsop-1973-me-nobug.mp4
├── WSOP 1978/ ~ WSOP 2001/
│   └── wsop-{연도}-me-nobug.mp4    # 메인 이벤트
├── WSOP 2002/
│   ├── 2002 World Series of Poker Part 1.mov
│   ├── 2002 World Series of Poker Part 2.mov
│   └── WSOP_2002_1.mxf, WSOP_2002_2.mxf
├── WSOP 2003/
│   ├── 2003 WSOP Best of Memorable Moments.mov
│   ├── 2003 WSOP Best of ALL INS.mov
│   ├── 2003 WSOP Best of Best Bluffs.mov
│   ├── 2003 WSOP Best of MONEYMAKER.mov
│   └── WSOP_2003-01.mxf ~ WSOP_2003-07.mxf
├── WSOP 2004/
│   ├── Generics/    # 제네릭 버전
│   ├── MOVs/        # MOV 포맷
│   └── MXFs/        # MXF 포맷 (WSOP_2004_1.mxf ~ 22.mxf)
├── WSOP 2005/
│   ├── Generic/
│   ├── MOVs/
│   └── MXFs/        # 32개 에피소드
├── WSOP 2006/ ~ WSOP 2016/
│   └── ...
```

**파일 포맷 종류**: `.avi`, `.mp4`, `.mov`, `.mxf`

**연도별 에피소드 수**:
| 연도 | 에피소드 수 | 비고 |
|------|------------|------|
| 1973-2001 | 1-2개 | 메인 이벤트만 |
| 2003 | 7개 + Best Of | Moneymaker 시즌 |
| 2004 | 22개 | Tournament of Champions 포함 |
| 2005 | 32개 | |
| 2006 | 34개 | |

---

#### 2.6.3 WSOP Bracelet Event - EUROPE

```
WSOP Bracelet Event/WSOP-EUROPE/
├── 2008 WSOP-Europe/
│   └── WSOPE08_Episode_{1-8}_H264.mov    # 8개 에피소드
├── 2009 WSOP-Europe/
│   └── WSOPE09_Episode_{1-10}_H264.mov   # 10개 에피소드 (일부 누락)
├── 2010 WSOP-Europe/
│   └── WSOPE10_Episode_{1-4}_H264.mov    # 4개 에피소드
├── 2011 WSOP-Europe/
│   └── WSOPE11_Episode_{1-5}_H264.mov    # 5개 에피소드
├── 2012 WSOP-Europe/
│   └── WSOPE12_Episode_{1-4}_H264.mov    # 4개 에피소드
├── 2013 WSOP-Europe/
│   └── WSE13-ME{01,02}_EuroSprt_NB_TEXT.mp4
├── 2021 WSOP-Europe/
│   ├── wsope-2021-10k-me-ft-004.mp4
│   ├── wsope-2021-10k-nlh6max-ft-009.mp4
│   ├── wsope-2021-1650-nlh6max-ft-010.mp4
│   └── wsope-2021-25k-platinumhighroller-ft-001.mp4
├── 2024 WSOP-Europe/
│   ├── #WSOPE 2024 NLH MAIN EVENT   DAY {1B-4}.mp4
│   ├── 100{3,4}_WSOPE_2024_50K DIAMOND HIGH ROLLER_DAY{1,2}.mp4
│   ├── 1009_WSOPE_2024_NLH_MAIN EVENT_DAY5.mp4
│   └── WE24-ME-{01-13}.mp4              # 클립 (13개)
└── 2025 WSOP-Europe/
    └── (준비중)
```

**파일명 패턴**:
- 2008-2012: `WSOPE{YY}_Episode_{번호}_H264.mov`
- 2021: `wsope-{연도}-{바이인}-{게임}-ft-{코드}.mp4`
- 2024 Stream: `#WSOPE {연도} {이벤트} DAY {번호}.mp4`
- 2024 Clip: `WE24-ME-{번호}.mp4`

---

#### 2.6.4 WSOP Bracelet Event - LAS VEGAS

```
WSOP Bracelet Event/WSOP-LAS VEGAS/
├── 2021 WSOP - LAS Vegas/           # 42개 파일
│   ├── 2021 WSOP Event #{번호} - {이벤트명} Final Table.mp4
│   └── 2021 WSOP Event #67 - Main Event Day {1A-9}.mp4
│
├── 2022 WSOP - LAS Vegas/           # 31개 파일
│   ├── 2022 WSOP Event #{번호} - {이벤트명} Final Table.mp4
│   └── 2022 WSOP Event #70 - Main Event Day {1D-9}.mp4
│
├── 2024 WSOP-LAS VEGAS (PokerGo Clip)/
│   ├── Clean/                        # 원본 클린 버전 (38개)
│   │   └── {번호}-wsop-2024-be-ev-{이벤트}-{내용}-clean.mp4
│   └── Mastered/                     # 마스터링 버전
│       └── {번호}-wsop-2024-be-ev-{이벤트}-{내용}.mp4
│
└── 2025 WSOP-LAS VEGAS/
    └── (준비중)
```

**2021/2022 파일명 패턴**:
```
2021 WSOP Event #{이벤트번호} - ${바이인} {게임종류} {이벤트타입}.mp4

예시:
2021 WSOP Event #67 - $10,000 No Limit Hold'em Main Event Day 1A Part 1.mp4
├─ 이벤트번호: 67
├─ 바이인: $10,000
├─ 게임: No Limit Hold'em
├─ 이벤트타입: Main Event
├─ Day: 1A
└─ Part: 1
```

**2024 PokerGo Clip 파일명 패턴**:
```
{번호}-wsop-{연도}-be-ev-{이벤트번호}-{바이인}-{게임}-{추가정보}.mp4

예시:
10-wsop-2024-be-ev-21-25k-nlh-hr-ft-schutten-reclaims-chip-lead.mp4
├─ 클립번호: 10
├─ 연도: 2024
├─ 타입: BE (Bracelet Event)
├─ 이벤트: 21
├─ 바이인: 25K
├─ 게임: NLH
├─ HR: High Roller
├─ FT: Final Table
└─ 내용: schutten-reclaims-chip-lead
```

---

#### 2.6.5 WSOP Bracelet Event - PARADISE

```
WSOP Bracelet Event/WSOP-PARADISE/
├── 2023 WSOP-PARADISE/
│   └── (내용 확인 필요)
└── 2024 WSOP-PARADISE SUPER MAIN EVENT/
    └── (내용 확인 필요)
```

---

#### 2.6.6 WSOP Circuit Event

```
WSOP Circuit Event/
├── WSOP Super Ciruit/
│   ├── 2023 WSOP International Super Circuit - London/
│   │   ├── ...Main Event Day 3.mp4        # 182GB
│   │   └── ...Main Event Day 4 (Final Table).mp4  # 107GB
│   │
│   └── 2025 WSOP Super Circuit Cyprus/
│       ├── $5M GTD   WSOP Super Circuit Cyprus Main Event - Day 1A.mp4
│       ├── $5M GTD   WSOP Super Circuit Cyprus Main Event - Day 1C.mp4
│       ├── $5M GTD   WSOP Super Circuit Cyprus Main Event - Day 2.mp4
│       ├── $5M GTD   WSOP Super Circuit Cyprus Main Event - Day 3.mp4
│       ├── $5M GTD   WSOP Super Circuit Cyprus Main Event - Day 4.mp4
│       └── $5M GTD   WSOP Super Circuit Cyprus Main Event - Final Day.mp4
│
└── WSOP-Circuit/
    └── 2024 WSOP Circuit LA/
        ├── 2024 WSOP-C LA STREAM/         # 풀 스트림 (11개)
        │   ├── 2024 WSOP Circuit Los Angeles - Beat the Legends [Invitational].mp4
        │   ├── 2024 WSOP Circuit Los Angeles - House Warming NL Hold'em [Day 2].mp4
        │   ├── 2024 WSOP Circuit Los Angeles - Main Event [Day 1A-2, Final Table].mp4
        │   ├── 2024 WSOP Circuit Los Angeles - Mystery Bounty NL Hold'em [Day 2].mp4
        │   └── 2024 WSOP Circuit Los Angeles - Tournament of Champions [Day 1-2, Final Table].mp4
        │
        └── 2024 WSOP-C LA SUBCLIP/        # 하이라이트 클립 (29개)
            └── WCLA24-{01-29}.mp4
```

**STREAM 파일명 패턴**:
```
2024 WSOP Circuit Los Angeles - {이벤트명} [{Day/Final}].mp4
```

**SUBCLIP 파일명 패턴**:
```
WCLA24-{번호}.mp4
├─ WCLA: WSOP Circuit LA
├─ 24: 2024년
└─ 번호: 01-29 (클립 번호)
```

---

## 3. 파일 포맷 요약

| 포맷 | 확장자 | 용도 | 주요 위치 |
|------|--------|------|----------|
| H.264/AVC | .mp4 | 최종 배포용 | 전체 |
| ProRes | .mov | 방송/편집용 | ARCHIVE (PRE-2016) |
| MXF | .mxf | 방송/아카이브 | ARCHIVE (PRE-2016) |
| AVI | .avi | 레거시 | 1973 |

---

## 4. 버전 관리 체계

| 버전 타입 | 설명 | 파일명 특징 |
|----------|------|------------|
| Clean | 원본 클린 버전 | `-clean`, `클린본` |
| Mastered | 마스터링 완료 | Mastered 폴더 |
| Stream | 풀 스트림 녹화 | STREAM 폴더 |
| Subclip | 하이라이트 클립 | SUBCLIP 폴더 |
| Final Edit | 최종 편집본 | `final_edit` |
| No Bug | 버그 없는 버전 | `-nobug` |

---

## 5. 데이터 통계

### 5.1 프로젝트별 파일 수 (추정)

| 프로젝트 | 파일 수 | 용량 (추정) |
|----------|---------|------------|
| GGMillions | 13 | ~100GB |
| GOG 최종 | 24 | ~50GB |
| HCL | 0 | 0 |
| MPP | 11 | ~100GB |
| PAD | 44 | ~200GB |
| WSOP Archive | 200+ | ~2TB |
| WSOP Bracelet | 150+ | ~3TB |
| WSOP Circuit | 50+ | ~500GB |
| **합계** | **500+** | **~6TB** |

### 5.2 연도별 WSOP 콘텐츠

| 연도 | Bracelet (LV) | Bracelet (EU) | Circuit | 합계 |
|------|--------------|---------------|---------|------|
| 2021 | 42 | 4 | - | 46 |
| 2022 | 31 | - | - | 31 |
| 2023 | - | - | 2 | 2 |
| 2024 | 38+ | 13+ | 40 | 91+ |
| 2025 | 준비중 | 준비중 | 6 | 6+ |

---

## 6. 파일명 파싱 규칙 요약

### 6.1 정규식 패턴

```python
# GGMillions
r'^(\d{6})?_?Super High Roller Poker FINAL TABLE with (.+)\.mp4$'

# PAD S12
r'^pad-s(\d+)-ep(\d+)-(\d+)\.mp4$'

# PAD S13
r'^PAD_S(\d+)_EP(\d+)_(.+)-(\d+)\.mp4$'

# WSOP 2024 Bracelet Clip
r'^(\d+)-wsop-(\d{4})-be-ev-(\d+)-(.+)\.mp4$'

# WSOP Circuit LA Subclip
r'^WCLA(\d{2})-(\d+)\.mp4$'

# WSOP Europe Episode
r'^WSOPE(\d{2})_Episode_(\d+)_H264\.mov$'
```

---

**문서 버전**: 1.0
**작성일**: 2025-12-09
**작성자**: AI Assistant
