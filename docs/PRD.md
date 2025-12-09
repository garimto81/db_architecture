# PRD: GGP Poker Video Catalog Database System
## 포커 콘텐츠 아카이빙 및 OTT 서비스 전문 DB (v3.0)

---

## 1. 개요 (Overview)

### 1.1 프로젝트 배경
GGP NAS에 저장된 다양한 포커 콘텐츠(WSOP, HCL, GGMillions, MPP 등)와 Google Sheets에 관리되는 핸드 분석 데이터를 통합 분석하여, 포커 전문 비디오 카탈로그 데이터베이스를 구축합니다. 이 DB는 포커 콘텐츠의 체계적인 아카이빙과 OTT 서비스 제공을 위한 핵심 시스템으로 활용됩니다.

### 1.2 프로젝트 목표
- 다중 포커 프로젝트(WSOP, HCL, GGMillions 등) 통합 관리
- NAS 폴더 구조 자동 스캔 및 메타데이터 수집
- Google Sheets 핸드 분석 데이터 연동 및 동기화
- 포커 특화 태그 시스템 (플레이 타입, 감정, 핸드 등급)
- 아카이빙 및 OTT 서비스를 위한 최적화된 데이터 구조

### 1.3 프로젝트 범위

#### In Scope
| 프로젝트 | 설명 | 콘텐츠 유형 | 파일 수 |
|----------|------|------------|---------|
| **WSOP** | World Series of Poker | 브레이슬릿 이벤트, 서킷 이벤트, 아카이브(1973~) | 400+ |
| **HCL** | Hustler Casino Live | 캐시게임, 하이라이트 클립 | 준비중 |
| **GGMillions** | Super High Roller Poker | 파이널 테이블 영상 | 13 |
| **GOG** | GOG 시리즈 | 에피소드 시리즈 (Final Edit + 클린본) | 24 |
| **MPP** | Mediterranean Poker Party | 토너먼트 영상 | 11 |
| **PAD** | Poker After Dark | TV 시리즈 (S12, S13) | 44 |

#### Out of Scope
- 실시간 스트리밍 인프라 (별도 프로젝트)
- 베팅/갬블링 기능

---

## 2. 현행 시스템 분석 (As-Is Analysis)

> 📁 **상세 폴더 구조**: [NAS_FOLDER_STRUCTURE.md](./NAS_FOLDER_STRUCTURE.md) 참조

### 2.1 NAS 폴더 구조 개요
**경로**: `\\10.10.100.122\docker\GGPNAs\ARCHIVE`

```
ARCHIVE/                              # 총 6TB+ 예상, 500+ 파일
│
├── GGMillions/                       # Super High Roller (13개)
│   └── {YYMMDD}_Super High Roller Poker FINAL TABLE with {플레이어}.mp4
│
├── GOG 최종/                         # GOG 시리즈 (12 에피소드 x 2 버전)
│   └── e{01-12}/
│       ├── E{번호}_GOG_final_edit_{날짜}.mp4
│       └── E{번호}_GOG_final_edit_클린본_{날짜}.mp4
│
├── HCL/                              # Hustler Casino Live (폴더만 존재)
│   ├── HCL Poker Clip/
│   │   └── {2023,2024,2025}/
│   └── SHOW, SERIES/
│
├── MPP/                              # Mediterranean Poker Party (11개)
│   └── 2025 MPP Cyprus/
│       ├── $1M GTD   $1K PokerOK Mystery Bounty/
│       ├── $2M GTD   $2K Luxon Pay Grand Final/
│       └── $5M GTD   $5K MPP Main Event/
│
├── PAD/                              # Poker After Dark (44개)
│   ├── PAD S12/                      # 시즌 12 (21 에피소드)
│   └── PAD S13/                      # 시즌 13 (23 에피소드)
│
└── WSOP/                             # World Series of Poker (400+)
    ├── WSOP ARCHIVE (PRE-2016)/      # 1973~2016 역사 아카이브
    │   └── WSOP {연도}/              # mov, mxf, avi, mp4 혼재
    │
    ├── WSOP Bracelet Event/          # 브레이슬릿 이벤트
    │   ├── WSOP-EUROPE/              # 2008-2013, 2021, 2024-2025
    │   ├── WSOP-LAS VEGAS/           # 2021, 2022, 2024, 2025
    │   │   └── 2024 WSOP-LAS VEGAS (PokerGo Clip)/
    │   │       ├── Clean/            # 원본 클린 버전
    │   │       └── Mastered/         # 마스터링 완료
    │   └── WSOP-PARADISE/            # 2023, 2024
    │
    └── WSOP Circuit Event/           # 서킷 이벤트
        ├── WSOP Super Ciruit/        # 2023 London, 2025 Cyprus
        └── WSOP-Circuit/
            └── 2024 WSOP Circuit LA/
                ├── 2024 WSOP-C LA STREAM/   # 풀 스트림 (11개)
                └── 2024 WSOP-C LA SUBCLIP/  # 하이라이트 (29개)
```

### 2.1.1 프로젝트별 파일 현황

| 프로젝트 | 파일 수 | 용량 (추정) | 상태 |
|----------|---------|------------|------|
| GGMillions | 13 | ~100GB | 활성 |
| GOG 최종 | 24 | ~50GB | 완료 |
| HCL | 0 | 0 | 준비중 |
| MPP | 11 | ~100GB | 활성 |
| PAD | 44 | ~200GB | 완료 |
| WSOP Archive | 200+ | ~2TB | 아카이브 |
| WSOP Bracelet | 150+ | ~3TB | 활성 |
| WSOP Circuit | 50+ | ~500GB | 활성 |
| **합계** | **500+** | **~6TB** | - |

### 2.2 파일명 패턴 분석

#### Pattern 1: WSOP Bracelet Event (Mastered)
```
{번호}-wsop-{연도}-be-ev-{이벤트번호}-{바이인}-{게임종류}-{추가정보}.mp4

예시:
10-wsop-2024-be-ev-21-25k-nlh-hr-ft-schutten-reclaims-chip-lead.mp4
├─ 번호: 10
├─ 연도: 2024
├─ 타입: BE (Bracelet Event)
├─ 이벤트: EV-21
├─ 바이인: 25K
├─ 게임: NLH (No Limit Hold'em)
├─ HR: High Roller
├─ FT: Final Table
└─ 내용: schutten-reclaims-chip-lead
```

#### Pattern 2: WSOP Circuit (SUBCLIP)
```
WCLA24-{번호}.mp4

예시:
WCLA24-15.mp4
├─ WCLA: WSOP Circuit LA
├─ 24: 2024년
└─ 번호: 15
```

#### Pattern 3: GGMillions
```
{날짜}_Super High Roller Poker FINAL TABLE with {플레이어}.mp4

예시:
250507_Super High Roller Poker FINAL TABLE with Joey Ingram.mp4
├─ 날짜: 2025-05-07
├─ 이벤트: Super High Roller Poker Final Table
└─ 주요 플레이어: Joey Ingram
```

### 2.3 Google Sheets 데이터 구조

#### Sheet 1: 핸드 분석 시트 (WSOP Circuit)
| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| File No. | 일련번호 | 1, 2, 3... |
| File Name | 토너먼트명 및 날짜 | WSOP Circuit LA Day 2 |
| Nas Folder Link | NAS 저장 경로 | \\\\...\\SUBCLIP\\ |
| In | 시작 타임코드 | 00:15:30 |
| Out | 종료 타임코드 | 00:16:45 |
| Hand Grade | 핸드 등급 (★~★★★) | ★★★ |
| Winner | 승자 최종 핸드 | Full House |
| Hands | 관련 플레이어 핸드 조합 | KK vs AA |
| Tag (Player) 1~3 | 참여 플레이어 (최대 3명) | Phil Ivey |
| Tag 1~7 (PokerPlay) | 포커 플레이 태그 | Preflop All-in, Cooler, Bad Beat |
| Tag 1~2 (Emotion) | 감정 태그 | Stressed, Excitement |

#### Sheet 2: 핸드 데이터베이스 (통합)
| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| id | UUID | 550e8400-e29b-41d4... |
| title | 핸드 제목 | 7-wsop-2024-be-ev-12-1500-nlh-ft |
| ProjectName | 프로젝트명 | WSOP, WSOP PARADISE |
| EpisodeEvent | 대회명 | $1,500 NLH, $50K PPC |
| Year_ | 연도 | 2024 |
| Location | 장소 | Las Vegas, Bahamas |
| Venue | 카지노명 | Atlantis, Horseshoe |
| Description | 핸드 설명 | River killer, Bad beat |
| PlayersTags | 참여 선수 | Phil Hellmuth, Daniel Negreanu |
| HANDTag | 카드 조합 | KK vs AA, AQ vs 99 |
| EPICHAND | 특별 핸드 | Straight Flush, Quads, Royal Flush |
| PokerPlayTags | 플레이 유형 | Cooler, Bluff, Hero Fold, Hero Call |
| HandGrade | 별점 | ★, ★★, ★★★ |
| Adjective | 형용사 | brutal, incredible, insane |
| Emotion | 감정 | intense, stressed, relief, excitement |
| RUNOUTTag | 결과 태그 | runner runner, 1out, dirty |

---

## 3. 페르소나 (Personas)

### 3.1 콘텐츠 아키비스트 (Content Archivist)
**이름**: 김영상
**역할**: 포커 비디오 콘텐츠 관리자

**목표**:
- NAS에 저장된 다양한 포커 프로젝트 영상을 체계적으로 분류
- 프로젝트별(WSOP/HCL/GGMillions) 누락 콘텐츠 파악
- Clean/Mastered 버전 관리

**Pain Points**:
- 프로젝트별 파일명 규칙이 다름
- STREAM vs SUBCLIP 구분 및 연결 어려움
- 연도별/이벤트별 영상 현황 파악 불가

**니즈**:
- 프로젝트별 자동 스캔 및 분류
- 파일 버전(Clean/Mastered/Subclip) 추적
- 아카이브 완결성 대시보드

---

### 3.2 포커 분석가 (Poker Analyst)
**이름**: 박분석
**역할**: 핸드 분석 및 콘텐츠 큐레이션

**목표**:
- Google Sheets의 핸드 분석 데이터를 DB와 연동
- 태그 기반 핸드 검색 (Cooler, Bad Beat, Hero Call 등)
- 플레이어별/이벤트별 핸드 통계

**Pain Points**:
- 시트 데이터와 실제 영상 파일 매칭 수동 작업
- 태그 일관성 유지 어려움
- In/Out 타임코드와 영상 연결 누락

**니즈**:
- 시트-영상 자동 매핑
- 태그 자동완성 및 표준화
- 타임코드 기반 영상 점프

---

### 3.3 OTT 서비스 운영자 (Service Operator)
**이름**: 이서비스
**역할**: 포커 OTT 플랫폼 운영

**목표**:
- WSOP Paradise, Circuit 등 프로젝트별 콘텐츠 서비스
- 하이라이트 클립 제공
- 다국어 자막 관리

**Pain Points**:
- 스트리밍 가능 파일(Mastered) 식별 어려움
- 프로젝트별 라이선스 관리 복잡
- 신규 콘텐츠 업데이트 지연

**니즈**:
- 프로젝트/품질별 파일 필터링
- 서비스 가능 상태 추적
- 자동 콘텐츠 업데이트 알림

---

### 3.4 포커 팬 (Poker Enthusiast)
**이름**: 최시청 (End User)
**역할**: 포커 콘텐츠 시청자

**목표**:
- 좋아하는 플레이어(Phil Ivey, Negreanu 등) 핸드 시청
- Epic Hand (Straight Flush, Quads) 검색
- Bad Beat, Cooler 같은 드라마틱한 장면 찾기

**Pain Points**:
- 플레이어/핸드 타입으로 검색 불가
- 하이라이트만 보고 싶을 때 풀영상만 있음
- 여러 프로젝트에 분산된 콘텐츠

**니즈**:
- 태그 기반 검색 (Emotion, PokerPlay)
- 핸드 등급(★★★) 필터
- 크로스 프로젝트 통합 검색

---

## 4. 기능 요구사항 (Functional Requirements)

### 4.1 데이터 수집 기능

#### 4.1.1 NAS 폴더 스캔
- [ ] 다중 프로젝트 폴더 구조 스캔 (WSOP, HCL, GGMillions, MPP, PAD)
- [ ] 프로젝트별 파일명 파서 구현
- [ ] Clean/Mastered/STREAM/SUBCLIP 버전 구분
- [ ] 미디어 메타데이터 추출 (해상도, 코덱, 재생시간)
- [ ] 파일 변경 감지 및 증분 스캔

#### 4.1.2 Google Sheets 연동
- [ ] 핸드 분석 시트 동기화 (Sheet 1)
- [ ] 핸드 데이터베이스 동기화 (Sheet 2)
- [ ] 태그 정규화 및 매핑 (PokerPlayTags, Emotion 등)
- [ ] In/Out 타임코드 파싱
- [ ] 양방향 동기화 (DB → Sheet 업데이트)

### 4.2 데이터베이스 기능

#### 4.2.1 프로젝트 관리
- [ ] 프로젝트 CRUD (WSOP, HCL, GGMillions 등)
- [ ] 프로젝트별 설정 (파일명 패턴, 폴더 구조)
- [ ] 프로젝트 통계 대시보드

#### 4.2.2 이벤트/에피소드 관리
- [ ] 이벤트 계층 구조 (프로젝트 > 시즌 > 이벤트 > 에피소드)
- [ ] 이벤트 유형 분류 (Bracelet, Circuit, Cash Game 등)
- [ ] 바이인/게임타입 필터링

#### 4.2.3 핸드 클립 관리
- [ ] 핸드 클립 CRUD
- [ ] 타임코드 기반 클립 정의 (In/Out)
- [ ] 다중 태그 시스템
  - PokerPlayTags (Cooler, Bluff, Hero Call 등)
  - Emotion (Stressed, Excitement, Relief 등)
  - HandGrade (★~★★★)
  - EPICHAND (Straight Flush, Quads 등)
  - RUNOUTTag (runner runner, dirty 등)
- [ ] 플레이어-핸드 연결 (최대 3명)

#### 4.2.4 검색 및 필터링
- [ ] 플레이어 이름 검색
- [ ] 태그 복합 검색 (AND/OR)
- [ ] 프로젝트/연도/이벤트 필터
- [ ] 핸드 등급 필터
- [ ] 감정/플레이 타입 필터

---

## 5. 데이터베이스 스키마 설계 (Database Schema)

### 5.1 핵심 엔티티 구조

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      GGP POKER VIDEO CATALOG DB                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐                                                           │
│  │   Project    │──┬──────────────────────────────────────────────┐        │
│  │  (프로젝트)  │  │                                              │        │
│  └──────────────┘  │                                              │        │
│         │          │                                              │        │
│         ▼          ▼                                              ▼        │
│  ┌──────────────┐  ┌──────────────┐     ┌──────────────┐  ┌──────────────┐│
│  │    Season    │─▶│    Event     │────▶│   Episode    │─▶│  VideoFile   ││
│  │    (시즌)    │  │   (이벤트)   │     │  (에피소드)  │  │ (비디오파일) ││
│  └──────────────┘  └──────────────┘     └──────────────┘  └──────────────┘│
│                           │                    │                 │         │
│                           ▼                    ▼                 ▼         │
│  ┌──────────────┐  ┌──────────────┐     ┌──────────────┐  ┌──────────────┐│
│  │    Player    │─▶│  EventResult │     │  HandClip    │─▶│    Tag       ││
│  │  (플레이어)  │  │  (결과기록)  │     │ (핸드클립)   │  │   (태그)     ││
│  └──────────────┘  └──────────────┘     └──────────────┘  └──────────────┘│
│         │                                      │                           │
│         ▼                                      ▼                           │
│  ┌──────────────┐                       ┌──────────────┐                   │
│  │  Bracelet    │                       │ HandClip_    │                   │
│  │ (브레이슬릿) │                       │   Player     │                   │
│  └──────────────┘                       └──────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 테이블 정의

#### 5.2.1 Project (프로젝트)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| code | VARCHAR(20) | 프로젝트 코드 (아래 enum 참조) |
| name | VARCHAR(200) | 프로젝트명 |
| description | TEXT | 설명 |
| nas_base_path | VARCHAR(500) | NAS 기본 경로 |
| filename_pattern | VARCHAR(500) | 파일명 패턴 (정규식) |
| is_active | BOOLEAN | 활성 여부 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |

**Project Code Enum** (7개):
```
WSOP        - World Series of Poker
HCL         - Hustler Casino Live
GGMILLIONS  - Super High Roller Poker (GGMillions)
MPP         - Mediterranean Poker Party
PAD         - Poker After Dark
GOG         - GOG 시리즈
OTHER       - 기타
```

#### 5.2.2 Season (시즌)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| project_id | UUID | 프로젝트 FK |
| year | INTEGER | 연도 |
| name | VARCHAR(200) | 시즌명 (예: "2024 WSOP Las Vegas") |
| location | VARCHAR(200) | 개최지 (Las Vegas, Paradise, Cyprus 등) |
| sub_category | VARCHAR(50) | WSOP 하위 분류 (아래 enum 참조) |
| start_date | DATE | 시작일 |
| end_date | DATE | 종료일 |
| status | VARCHAR(20) | active/completed/upcoming |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |

**Sub-Category Enum** (WSOP 전용):
```
ARCHIVE         - WSOP ARCHIVE (PRE-2016)
BRACELET_LV     - WSOP Bracelet Event - Las Vegas
BRACELET_EU     - WSOP Bracelet Event - Europe
BRACELET_PARA   - WSOP Bracelet Event - Paradise
CIRCUIT         - WSOP Circuit Event
SUPER_CIRCUIT   - WSOP Super Circuit
NULL            - 기타 프로젝트는 NULL
```

> **설계 변경**: `venue` 컬럼을 Season에서 제거하고 Event로 이동 (venue는 이벤트 속성)

#### 5.2.3 Event (이벤트)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| season_id | UUID | 시즌 FK |
| event_number | INTEGER | 이벤트 번호 (예: 21, 43) |
| name | VARCHAR(500) | 이벤트명 (예: "$1,500 No-Limit Hold'em") |
| name_short | VARCHAR(100) | 약칭 (예: "1500-nlh", "50k-ppc") |
| event_type | VARCHAR(50) | bracelet/circuit/high_roller/cash_game/super_high_roller |
| game_type | VARCHAR(50) | NLHE/PLO/Mixed/Stud/2-7TD 등 |
| buy_in | DECIMAL(10,2) | 바이인 금액 (USD) |
| gtd_amount | DECIMAL(15,2) | 보장 상금 (GTD) - MPP/Circuit용 |
| venue | VARCHAR(200) | 카지노/장소명 (Season에서 이동) |
| entry_count | INTEGER | 참가자 수 |
| prize_pool | DECIMAL(15,2) | 상금풀 |
| start_date | DATE | 시작일 |
| end_date | DATE | 종료일 |
| total_days | INTEGER | 진행 일수 |
| status | VARCHAR(20) | upcoming/in_progress/completed |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |

**Event Type Enum**:
```
bracelet         - WSOP 브레이슬릿 이벤트
circuit          - WSOP 서킷 이벤트
super_circuit    - WSOP 슈퍼 서킷
high_roller      - 하이롤러
super_high_roller - 슈퍼 하이롤러 (GGMillions)
cash_game        - 캐시 게임 (HCL)
tv_series        - TV 시리즈 (PAD, GOG)
mystery_bounty   - 미스터리 바운티
main_event       - 메인 이벤트
```

#### 5.2.4 Episode (에피소드/영상 단위)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| event_id | UUID | 이벤트 FK |
| episode_number | INTEGER | 에피소드 번호 |
| day_number | INTEGER | Day 번호 (Day 1, Day 2...) |
| part_number | INTEGER | 파트 번호 |
| title | VARCHAR(500) | 에피소드 제목 |
| episode_type | VARCHAR(50) | full/highlight/recap/interview/subclip |
| table_type | VARCHAR(50) | preliminary/day1/day2/final_table/heads_up |
| duration_seconds | INTEGER | 재생시간(초) |
| air_date | DATE | 방송일 |
| synopsis | TEXT | 설명 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |

#### 5.2.5 VideoFile (비디오 파일)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| episode_id | UUID | 에피소드 FK |
| file_path | VARCHAR(1000) | NAS 전체 경로 |
| file_name | VARCHAR(500) | 파일명 |
| file_size_bytes | BIGINT | 파일 크기 |
| file_format | VARCHAR(20) | 파일 포맷 (아래 enum 참조) |
| resolution | VARCHAR(20) | 1080p/4K 등 |
| video_codec | VARCHAR(50) | 비디오 코덱 |
| audio_codec | VARCHAR(50) | 오디오 코덱 |
| bitrate_kbps | INTEGER | 비트레이트 |
| duration_seconds | INTEGER | 재생시간 |
| version_type | VARCHAR(20) | 버전 타입 (아래 enum 참조) |
| is_original | BOOLEAN | 원본 여부 |
| checksum | VARCHAR(64) | 파일 체크섬 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |

**File Format Enum** (NAS 분석 결과):
```
mp4     - H.264/AVC 최종 배포용
mov     - ProRes 방송/편집용
mxf     - MXF 방송/아카이브용
avi     - 레거시 포맷 (1973 등)
mkv     - Matroska 컨테이너
```

**Version Type Enum** (NAS 분석 결과):
```
clean       - 원본 클린 버전 (-clean, 클린본)
mastered    - 마스터링 완료 (Mastered 폴더)
stream      - 풀 스트림 녹화 (STREAM 폴더)
subclip     - 하이라이트 클립 (SUBCLIP 폴더)
final_edit  - 최종 편집본 (final_edit)
nobug       - 버그 없는 버전 (-nobug)
pgm         - PGM 버전 (Google Sheets Source 컬럼)
generic     - 제네릭 버전 (Generics 폴더)
hires       - 고해상도 버전 (HiRes)
```

#### 5.2.6 Player (플레이어)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| name | VARCHAR(200) | 이름 (영문) |
| name_display | VARCHAR(200) | 표시명 (별명 포함) |
| nationality | VARCHAR(100) | 국적 |
| hendon_mob_id | VARCHAR(50) | Hendon Mob ID |
| total_live_earnings | DECIMAL(15,2) | 총 라이브 상금 |
| wsop_bracelets | INTEGER | WSOP 브레이슬릿 수 |
| profile_image_url | VARCHAR(1000) | 프로필 이미지 |
| is_active | BOOLEAN | 현역 여부 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |

#### 5.2.7 Tag (태그)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| category | VARCHAR(50) | 태그 카테고리 (아래 참조) |
| name | VARCHAR(100) | 태그명 (정규화된 값) |
| name_display | VARCHAR(100) | 표시명 (UI용) |
| description | TEXT | 설명 |
| sort_order | INTEGER | 정렬 순서 |

**Tag Category Enum** (6개, Google Sheets 분석 결과):
| 카테고리 | 설명 | 저장 방식 |
|----------|------|----------|
| `poker_play` | 포커 플레이 태그 | Tag 테이블 |
| `emotion` | 감정 태그 | Tag 테이블 |
| `epic_hand` | 특별 핸드 | Tag 테이블 |
| `runout` | 런아웃 태그 | Tag 테이블 |
| `adjective` | 형용사 태그 | Tag 테이블 |
| `hand_grade` | 핸드 등급 | **HandClip.hand_grade에 직접 저장** (★~★★★ 고정값) |

**기본 태그 시드 데이터**:
```
poker_play (9개):
  - preflop_allin (Preflop All-in)
  - cooler (Cooler)
  - bad_beat (Bad Beat)
  - bluff (Bluff)
  - hero_call (Hero Call)
  - hero_fold (Hero Fold)
  - suckout (Suckout)
  - slow_play (Slow Play)
  - value_bet (Value Bet)

emotion (6개):
  - stressed (Stressed)
  - excitement (Excitement)
  - relief (Relief)
  - intense (Intense)
  - shocked (Shocked)
  - disappointed (Disappointed)

epic_hand (4개):
  - royal_flush (Royal Flush)
  - straight_flush (Straight Flush)
  - quads (Quads)
  - full_house_over (Full House over Full House)

runout (4개):
  - runner_runner (Runner Runner)
  - one_out (1 Out)
  - dirty (Dirty)
  - clean (Clean)

adjective (5개):
  - brutal (Brutal)
  - incredible (Incredible)
  - insane (Insane)
  - sick (Sick)
  - amazing (Amazing)
```

> **설계 결정**: `hand_grade`(★~★★★)는 고정값이므로 Tag 테이블에 저장하지 않고 HandClip.hand_grade에 직접 저장 (join 오버헤드 제거)

#### 5.2.8 HandClip (핸드 클립)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| episode_id | UUID | 에피소드 FK |
| video_file_id | UUID | 비디오파일 FK |
| clip_number | INTEGER | 클립 번호 (File No.) |
| title | VARCHAR(500) | 클립 제목 |
| timecode_in | VARCHAR(20) | 시작 타임코드 (HH:MM:SS) |
| timecode_out | VARCHAR(20) | 종료 타임코드 |
| start_seconds | INTEGER | 시작 초 |
| end_seconds | INTEGER | 종료 초 |
| winner_hand | VARCHAR(100) | 승자 최종 핸드 |
| hands_involved | VARCHAR(200) | 관련 핸드 (예: "KK vs AA") |
| description | TEXT | 핸드 설명 |
| hand_grade | VARCHAR(10) | 핸드 등급 (★~★★★) |
| sheet_row_number | INTEGER | 원본 시트 행 번호 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |

#### 5.2.9 HandClip_Tag (핸드클립-태그 연결)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| hand_clip_id | UUID | 핸드클립 FK |
| tag_id | UUID | 태그 FK |
| tag_order | INTEGER | 태그 순서 (1~7) |

#### 5.2.10 HandClip_Player (핸드클립-플레이어 연결)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| hand_clip_id | UUID | 핸드클립 FK |
| player_id | UUID | 플레이어 FK |
| player_order | INTEGER | 플레이어 순서 (1~3) |
| role | VARCHAR(20) | winner/loser/involved |
| hole_cards | VARCHAR(20) | 홀카드 (예: "AsKs") |

#### 5.2.11 EventResult (이벤트 결과)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| event_id | UUID | 이벤트 FK |
| player_id | UUID | 플레이어 FK |
| finish_position | INTEGER | 최종 순위 |
| prize_amount | DECIMAL(15,2) | 상금 |
| is_winner | BOOLEAN | 우승 여부 |
| is_final_table | BOOLEAN | 파이널 테이블 진출 여부 |

#### 5.2.12 Bracelet (브레이슬릿)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| player_id | UUID | 플레이어 FK |
| event_id | UUID | 이벤트 FK |
| bracelet_number | INTEGER | N번째 브레이슬릿 |
| prize_amount | DECIMAL(15,2) | 우승 상금 |
| win_date | DATE | 우승일 |

#### 5.2.13 GoogleSheetSync (시트 동기화)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| sheet_id | VARCHAR(200) | 구글 시트 ID |
| sheet_name | VARCHAR(200) | 시트명/탭명 |
| sheet_url | VARCHAR(500) | 시트 URL |
| entity_type | VARCHAR(50) | hand_clip/event/player |
| last_synced_at | TIMESTAMP | 마지막 동기화 |
| last_row_synced | INTEGER | 마지막 동기화 행 번호 (증분용) |
| sync_status | VARCHAR(20) | success/failed/pending/running |
| row_count | INTEGER | 동기화된 행 수 |
| new_rows_count | INTEGER | 신규 추가된 행 수 |
| updated_rows_count | INTEGER | 수정된 행 수 |
| error_message | TEXT | 에러 메시지 |
| created_at | TIMESTAMP | 생성일시 |

#### 5.2.14 NasScanCheckpoint (NAS 스캔 체크포인트)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| project_code | VARCHAR(20) | 프로젝트 코드 (WSOP, HCL 등) |
| scan_path | VARCHAR(1000) | 스캔 대상 경로 |
| last_scanned_at | TIMESTAMP | 마지막 스캔 시간 |
| last_file_mtime | TIMESTAMP | 마지막 파일 수정시간 |
| total_files | INTEGER | 총 파일 수 |
| new_files_count | INTEGER | 신규 파일 수 |
| scan_status | VARCHAR(20) | success/failed/running |
| scan_duration_sec | INTEGER | 스캔 소요시간 (초) |
| error_message | TEXT | 에러 메시지 |
| created_at | TIMESTAMP | 생성일시 |

#### 5.2.15 SyncLog (동기화 로그)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| sync_type | VARCHAR(20) | nas_scan/sheet_sync/full_sync |
| source | VARCHAR(100) | 소스 (시트명 또는 NAS 경로) |
| started_at | TIMESTAMP | 시작 시간 |
| finished_at | TIMESTAMP | 종료 시간 |
| status | VARCHAR(20) | success/failed/partial |
| records_processed | INTEGER | 처리된 레코드 수 |
| records_created | INTEGER | 생성된 레코드 수 |
| records_updated | INTEGER | 수정된 레코드 수 |
| records_failed | INTEGER | 실패한 레코드 수 |
| error_details | JSONB | 에러 상세 (JSON) |

#### 5.2.16 ChangeHistory (변경 이력)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 기본키 |
| entity_type | VARCHAR(50) | video_file/hand_clip/player 등 |
| entity_id | UUID | 변경된 엔티티 ID |
| change_type | VARCHAR(20) | create/update/delete |
| changed_fields | JSONB | 변경된 필드 목록 |
| old_values | JSONB | 이전 값 |
| new_values | JSONB | 새 값 |
| change_source | VARCHAR(50) | nas_scan/sheet_sync/manual/api |
| changed_at | TIMESTAMP | 변경 시간 |
| changed_by | VARCHAR(100) | 변경자 (시스템/사용자) |

---

## 6. 데이터 소스 연동

### 6.1 NAS 연결 정보
```
서버: \\10.10.100.122
공유폴더: docker\GGPNAs\ARCHIVE
사용자: GGP
```

### 6.2 Google Sheets 연동
| 시트 ID | 용도 | 설명 |
|---------|------|------|
| 1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4 | 핸드 분석 시트 | WSOP Circuit 핸드 분석 (38건) |
| 1pUMPKe-OsKc-Xd8lH1cP9ctJO4hj3keXY5RwNFp2Mtk | 핸드 데이터베이스 | 통합 핸드 메타데이터 |

---

## 7. 기존 시스템 통합 전략

### 7.1 archive-analyzer 프로젝트 연동

기존 `archive-analyzer` 프로젝트의 `pokervod.db`와 연동 전략:

| PRD 테이블 | pokervod.db 기존 테이블 | 통합 방안 |
|-----------|----------------------|----------|
| Project | catalogs | 확장 (code, filename_pattern 추가) |
| Season | series | 확장 (sub_category, location 추가) |
| Event | **신규** | 신규 생성 |
| Episode | contents | 확장 (day_number, part_number 추가) |
| VideoFile | files | 확장 (version_type enum 확장) |
| Player | players | 확장 (hendon_mob_id 등 추가) |
| Tag | tags | 확장 (category 추가) |
| HandClip | **신규** | 신규 생성 (기존 hands 대체) |
| HandClip_Tag | content_tags 패턴 | 패턴 재사용 |
| HandClip_Player | content_players 패턴 | 패턴 재사용 |
| EventResult | **신규** | 신규 생성 |
| Bracelet | **신규** | 신규 생성 |
| GoogleSheetSync | **신규** | 신규 생성 |

### 7.2 데이터 동기화

```
archive-analyzer                 db_architecture (PRD)
─────────────────                ───────────────────
catalogs          ←───확장───→   Project
series            ←───확장───→   Season
                  ←───신규───→   Event
contents          ←───확장───→   Episode
files             ←───확장───→   VideoFile
tags              ←───확장───→   Tag
players           ←───확장───→   Player
                  ←───신규───→   HandClip
                  ←───신규───→   EventResult
                  ←───신규───→   Bracelet
```

### 7.3 Google Sheets 동기화 재사용

기존 `archive-analyzer`의 sheets_sync 모듈 재사용:
- `sheets_sync.py`: 12개 테이블 양방향 동기화
- `archive_hands_sync.py`: 핸드 데이터 동기화
- Rate Limit 대응 (60 req/min)
- Exponential Backoff 구현

---

## 8. 기술 스택 (Tech Stack)

### 8.1 데이터베이스
- **Primary DB**: PostgreSQL 15+
  - JSONB 지원
  - Full-Text Search
  - 대용량 데이터 처리

### 8.2 데이터 수집/처리
- **NAS 스캔**: Python + SMB/CIFS
- **파일명 파서**: 프로젝트별 정규식 엔진
- **미디어 분석**: FFprobe
- **Google Sheets**: Google Sheets API v4

### 8.3 API 서버
- Python FastAPI
- GraphQL (복잡 쿼리용)

---

## 8. 자동 동기화 시스템 (Auto-Sync System)

### 8.1 개요

NAS와 Google Sheets에 지속적으로 추가되는 데이터를 **1시간마다** 자동으로 감지하고 DB에 반영하는 **Docker 기반** 시스템.

```
┌─────────────────────────────────────────────────────────────────┐
│                 DOCKER-BASED AUTO-SYNC ARCHITECTURE              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    docker-compose.yml                    │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│          ┌───────────────────┼───────────────────┐              │
│          ▼                   ▼                   ▼              │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐      │
│   │  postgres   │     │ sync-worker │     │   redis     │      │
│   │  (DB)       │     │ (1시간 간격)│     │  (Queue)    │      │
│   └─────────────┘     └──────┬──────┘     └─────────────┘      │
│          ▲                   │                   ▲              │
│          │                   ▼                   │              │
│          │    ┌──────────────────────────────┐   │              │
│          │    │        SYNC ENGINE           │   │              │
│          │    │  ┌────────┐  ┌────────────┐  │   │              │
│          │    │  │  NAS   │  │  Sheets    │  │   │              │
│          │    │  │Scanner │  │  Parser    │  │   │              │
│          │    │  └────────┘  └────────────┘  │   │              │
│          │    └──────────────────────────────┘   │              │
│          │                   │                   │              │
│          └───────────────────┴───────────────────┘              │
│                                                                  │
│   Volumes:                                                       │
│   - postgres_data:/var/lib/postgresql/data                      │
│   - /mnt/nas:/nas:ro  (NAS SMB 마운트)                          │
│   - ./config:/app/config                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Docker Compose 구성

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: pokervod-db
    environment:
      POSTGRES_DB: pokervod
      POSTGRES_USER: ${DB_USER:-pokervod}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pokervod"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: pokervod-redis
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

  sync-worker:
    build:
      context: .
      dockerfile: Dockerfile.sync
    container_name: pokervod-sync
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    environment:
      DATABASE_URL: postgresql://${DB_USER:-pokervod}:${DB_PASSWORD}@postgres:5432/pokervod
      REDIS_URL: redis://redis:6379/0
      NAS_MOUNT_PATH: /nas
      SYNC_INTERVAL_HOURS: 1
      GOOGLE_CREDENTIALS_PATH: /app/config/gcp-service-account.json
      SPREADSHEET_ID: ${SPREADSHEET_ID}
    volumes:
      - /mnt/nas:/nas:ro                    # NAS SMB 마운트 (읽기 전용)
      - ./config:/app/config:ro             # 설정 파일
      - ./logs:/app/logs                    # 로그 디렉토리
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### 8.3 Sync Worker Dockerfile

```dockerfile
# Dockerfile.sync
FROM python:3.11-slim

WORKDIR /app

# FFprobe 설치 (미디어 분석용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

# 1시간마다 실행하는 스케줄러
CMD ["python", "-m", "src.sync_scheduler"]
```

### 8.4 NAS 증분 스캔

#### 8.4.1 스캔 전략

| 전략 | 설명 | 적용 |
|------|------|------|
| **mtime 기반** | 파일 수정시간으로 변경 감지 | 기본 전략 |
| **체크섬 비교** | 파일 해시값 비교 | 의심 파일만 |
| **폴더 워치** | 신규 폴더 감지 | 실시간 모드 |

#### 8.4.2 스캔 프로세스

```python
# 증분 스캔 알고리즘 (pseudo-code)
def incremental_scan(project_code: str):
    checkpoint = get_checkpoint(project_code)
    last_mtime = checkpoint.last_file_mtime

    # 1. 신규/수정 파일 감지
    new_files = scan_newer_than(last_mtime)

    # 2. 파일명 파싱 및 메타데이터 추출
    for file in new_files:
        metadata = parse_filename(file, project_code)
        media_info = extract_media_info(file)  # FFprobe

        # 3. DB Upsert
        upsert_video_file(metadata, media_info)

        # 4. 자동 분류 (Episode 매칭)
        episode = match_episode(metadata)
        if episode:
            link_file_to_episode(file, episode)

    # 5. 체크포인트 업데이트
    update_checkpoint(project_code, max_mtime)
```

#### 8.4.3 스캔 주기

| 모드 | 주기 | 사용 시점 | Docker 환경변수 |
|------|------|----------|----------------|
| **기본** | 1시간 | 평상시 | `SYNC_INTERVAL_HOURS=1` |
| **긴급** | 15분 | 대회 진행 중 | `SYNC_INTERVAL_HOURS=0.25` |
| **배치** | 1일 1회 | 전체 검증 | cron: `0 3 * * *` |
| **수동** | On-demand | 긴급 업데이트 | `docker exec pokervod-sync python -m src.manual_sync` |

### 8.5 Google Sheets 증분 동기화

#### 8.5.1 동기화 전략

| 전략 | 설명 | 적용 |
|------|------|------|
| **행 번호 기반** | last_row_synced 이후 행만 처리 | 신규 데이터 |
| **수정시간 기반** | 셀 수정 시간 확인 (API 지원 시) | 수정 데이터 |
| **전체 비교** | 해시 비교로 변경 감지 | 주기적 검증 |

#### 8.5.2 충돌 해결 정책

| 충돌 유형 | 정책 | 설명 |
|----------|------|------|
| **동일 ID, 다른 값** | Sheet 우선 | 시트가 마스터 데이터 |
| **DB에만 존재** | 유지 | NAS 스캔 데이터 보존 |
| **Sheet에만 존재** | 생성 | 신규 데이터 추가 |
| **양쪽 다 수정됨** | 수동 확인 | conflict 플래그 설정 |

#### 8.5.3 Rate Limit 대응

```
Google Sheets API 제한: 60 req/min per user

대응 전략:
1. Exponential Backoff (1s → 2s → 4s → 8s → 최대 60s)
2. 배치 요청 (100행씩 묶어서)
3. 캐시 활용 (변경 없으면 스킵)
4. 요청 큐잉 (Redis 기반)
```

### 8.6 동기화 스케줄 설정

```yaml
# config/sync_schedule.yaml (Docker 볼륨 마운트)
schedules:
  # 기본: 1시간 간격 (환경변수 SYNC_INTERVAL_HOURS로 오버라이드 가능)
  default_interval_hours: 1

  nas_scan:
    - project: WSOP
      cron: "0 * * * *"        # 1시간마다
      enabled: true
    - project: HCL
      cron: "0 * * * *"        # 1시간마다
      enabled: false           # 데이터 없음
    - project: GGMillions
      cron: "0 * * * *"        # 1시간마다
      enabled: true
    - project: ALL
      cron: "0 3 * * *"        # 매일 03:00 전체 스캔
      enabled: true

  sheet_sync:
    - sheet: hand_analysis
      cron: "0 * * * *"        # 1시간마다
      enabled: true
    - sheet: hand_database
      cron: "0 * * * *"        # 1시간마다
      enabled: true

  full_validation:
    cron: "0 4 * * 0"          # 매주 일요일 04:00
    enabled: true
```

### 8.7 Docker 운영 명령어

```bash
# 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f sync-worker

# 수동 동기화 실행
docker exec pokervod-sync python -m src.manual_sync --all

# NAS만 스캔
docker exec pokervod-sync python -m src.manual_sync --nas-only

# Sheets만 동기화
docker exec pokervod-sync python -m src.manual_sync --sheets-only

# 동기화 상태 확인
docker exec pokervod-sync python -m src.sync_status

# DB 접속
docker exec -it pokervod-db psql -U pokervod -d pokervod

# 컨테이너 재시작 (설정 변경 후)
docker-compose restart sync-worker
```

### 8.8 알림 및 모니터링

#### 8.8.1 알림 트리거

| 이벤트 | 심각도 | 알림 채널 |
|--------|--------|----------|
| 신규 파일 감지 | INFO | 로그 |
| 동기화 완료 | INFO | 로그 |
| 동기화 실패 | ERROR | Slack/Email |
| 파일명 파싱 실패 | WARN | 로그 + 대시보드 |
| Rate Limit 도달 | WARN | 로그 |
| 충돌 발생 | WARN | Slack |
| 24시간 미동기화 | ERROR | Slack/Email |

#### 8.8.2 대시보드 메트릭

| 메트릭 | 설명 |
|--------|------|
| sync_latency_seconds | 동기화 지연 시간 |
| new_files_per_hour | 시간당 신규 파일 수 |
| sync_success_rate | 동기화 성공률 |
| parsing_failure_rate | 파싱 실패율 |
| pending_conflicts | 미해결 충돌 수 |

### 8.9 데이터 정합성 검증

#### 8.9.1 검증 규칙

```sql
-- 1. 파일 존재 검증 (NAS ↔ DB)
SELECT vf.* FROM video_files vf
WHERE NOT EXISTS (
    SELECT 1 FROM nas_file_check(vf.file_path)
);

-- 2. 시트-DB 일치 검증
SELECT hc.* FROM hand_clips hc
JOIN google_sheet_sync gs ON gs.entity_type = 'hand_clip'
WHERE hc.sheet_row_number > gs.last_row_synced;

-- 3. 고아 레코드 검증 (FK 무결성)
SELECT hc.* FROM hand_clips hc
LEFT JOIN video_files vf ON hc.video_file_id = vf.id
WHERE vf.id IS NULL;
```

#### 8.9.2 자동 복구

| 문제 | 자동 복구 |
|------|----------|
| NAS 파일 삭제됨 | `status = 'deleted'` 마킹 |
| 시트 행 삭제됨 | 소프트 삭제 (deleted_at 설정) |
| FK 무결성 위반 | 경고 로그 + 수동 확인 대기 |

---

## 9. 구현 로드맵 (Implementation Roadmap)

### Phase 1: 기반 구축 (Week 1-2)
- [ ] DB 스키마 생성 (Core 16개 테이블)
- [ ] 프로젝트/태그 마스터 데이터 입력
- [ ] NAS 연결 및 기본 스캔 구현
- [ ] 파일명 파서 프레임워크 구축

### Phase 2: 데이터 수집 (Week 3-4)
- [ ] 프로젝트별 파일명 파서 개발 (7개 프로젝트)
- [ ] Google Sheets 연동 구현 (gspread)
- [ ] 기존 핸드 클립 데이터 마이그레이션
- [ ] 초기 전체 스캔 실행

### Phase 3: 자동 동기화 (Week 5-6)
- [ ] NAS 증분 스캔 구현 (mtime 기반)
- [ ] Google Sheets 증분 동기화 구현
- [ ] 스케줄러 설정 (APScheduler/Celery)
- [ ] 충돌 해결 로직 구현

### Phase 4: 모니터링 & 알림 (Week 7-8)
- [ ] SyncLog/ChangeHistory 테이블 활용
- [ ] 대시보드 구현 (Grafana/custom)
- [ ] Slack/Email 알림 연동
- [ ] 데이터 정합성 검증 스크립트

### Phase 5: 기능 확장 (Week 9+)
- [ ] 태그 기반 검색 시스템 (MeiliSearch)
- [ ] 타임코드 기반 영상 점프
- [ ] 플레이어 통계 대시보드
- [ ] API 서버 (FastAPI)

---

## 10. 성공 지표 (Success Metrics)

### 10.1 데이터 품질

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| NAS 파일 자동 매핑률 | 85% 이상 | 파싱 성공 파일 / 전체 파일 |
| Google Sheets 동기화 성공률 | 99% 이상 | 성공 동기화 / 전체 시도 |
| 태그 검색 정확도 | 95% 이상 | 관련 결과 / 검색 결과 |
| 플레이어 검색 정확도 | 95% 이상 | 정확한 매칭 / 검색 결과 |

### 10.2 자동 동기화

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 증분 스캔 지연 | < 10분 | 파일 생성 ~ DB 반영 시간 |
| 시트 동기화 지연 | < 5분 | 시트 수정 ~ DB 반영 시간 |
| 동기화 실패율 | < 1% | 실패 횟수 / 전체 시도 |
| 충돌 발생률 | < 0.1% | 충돌 건수 / 전체 레코드 |

### 10.3 시스템 안정성

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 시스템 가용성 | 99.5% 이상 | Uptime 모니터링 |
| API 응답 시간 | < 500ms (P95) | 응답 시간 분포 |
| 배치 작업 성공률 | 99% 이상 | 성공 배치 / 전체 배치 |

---

## 11. 부록

### 11.1 포커 용어
- **WSOP**: World Series of Poker
- **HCL**: Hustler Casino Live
- **Bracelet**: WSOP 우승 팔찌
- **NLHE**: No Limit Texas Hold'em
- **PLO**: Pot Limit Omaha
- **Cooler**: 양쪽 다 강한 핸드로 필연적 대결
- **Bad Beat**: 유리한 상황에서 역전패
- **Hero Call**: 블러프 캐치 콜
- **Runner Runner**: 턴+리버 연속 아웃

### 11.2 태그 상세 정의

#### PokerPlayTags
| 태그 | 설명 |
|------|------|
| Preflop All-in | 프리플랍 올인 |
| Cooler | 쿨러 (양쪽 강핸드) |
| Bad Beat | 배드빗 |
| Bluff | 블러프 |
| Hero Call | 히어로 콜 |
| Hero Fold | 히어로 폴드 |
| Suckout | 역전 |
| Slow Play | 슬로우 플레이 |
| Value Bet | 밸류벳 |

#### Emotion
| 태그 | 설명 |
|------|------|
| Stressed | 긴장/스트레스 |
| Excitement | 흥분 |
| Relief | 안도 |
| Intense | 긴장감 고조 |
| Shocked | 충격 |
| Disappointed | 실망 |

---

**문서 버전**: 5.1
**작성일**: 2025-12-09
**작성자**: AI Assistant
**상태**: Docker 기반 자동 동기화 시스템 설계 완료

### 변경 이력
| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0 | 2025-12-09 | 초안 작성 |
| 2.0 | 2025-12-09 | WSOP 전문 DB로 업데이트 |
| 3.0 | 2025-12-09 | 실제 NAS/Google Sheets 분석 반영 |
| 3.1 | 2025-12-09 | NAS 폴더 구조 상세 분석, GOG 프로젝트 추가 |
| 4.0 | 2025-12-09 | 스키마 대폭 개선: Project/Season/Event/VideoFile/Tag enum 확장, archive-analyzer 통합 전략 |
| 5.0 | 2025-12-09 | 자동 동기화 시스템 추가: 신규 테이블 4개, 증분 스캔/동기화, 충돌 해결, 모니터링 |
| **5.1** | **2025-12-09** | **Docker 기반 아키텍처**: (1) docker-compose.yml 추가 (postgres, redis, sync-worker), (2) 동기화 주기 1시간으로 통일, (3) Dockerfile.sync 추가, (4) Docker 운영 명령어 섹션 추가, (5) 환경변수 기반 설정 |
