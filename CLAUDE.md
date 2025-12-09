# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

GGP Poker Video Catalog Database - 포커 콘텐츠 아카이빙 및 OTT 서비스를 위한 DB 설계 프로젝트

**목적**: NAS에 저장된 포커 영상(WSOP, HCL, GGMillions, MPP, PAD)과 Google Sheets 핸드 분석 데이터를 통합하는 데이터베이스 설계

**현재 상태**: 설계 단계 (PRD 완료)

## 핵심 문서

| 문서 | 경로 | 내용 |
|------|------|------|
| PRD | `docs/PRD.md` | 전체 요구사항, DB 스키마, 로드맵 |
| NAS 구조 | `docs/NAS_FOLDER_STRUCTURE.md` | 폴더별 파일명 패턴, 파싱 규칙 |

## 데이터 소스

### NAS
- 경로: `\\10.10.100.122\docker\GGPNAs\ARCHIVE`
- 6개 프로젝트: GGMillions, GOG, HCL, MPP, PAD, WSOP
- 총 500+ 파일, ~6TB

### Google Sheets
- 핸드 분석 시트: `1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4`
- 핸드 DB: `1pUMPKe-OsKc-Xd8lH1cP9ctJO4hj3keXY5RwNFp2Mtk`

## 파일명 파싱 패턴 (정규식)

```python
# GGMillions
r'^(\d{6})?_?Super High Roller Poker FINAL TABLE with (.+)\.mp4$'

# PAD (시즌 12/13)
r'^pad-s(\d+)-ep(\d+)-(\d+)\.mp4$'
r'^PAD_S(\d+)_EP(\d+)_(.+)-(\d+)\.mp4$'

# WSOP 2024 Bracelet Clip
r'^(\d+)-wsop-(\d{4})-be-ev-(\d+)-(.+)\.mp4$'

# WSOP Circuit LA Subclip
r'^WCLA(\d{2})-(\d+)\.mp4$'
```

## 기술 스택 (계획)

- **DB**: PostgreSQL 15+ (JSONB, Full-Text Search)
- **API**: Python FastAPI
- **NAS 스캔**: Python + SMB/CIFS
- **미디어 분석**: FFprobe
- **시트 연동**: Google Sheets API v4

## DB 스키마 핵심 엔티티

```
Project → Season → Event → Episode → VideoFile
                      ↓         ↓
                  EventResult  HandClip → Tag, Player
```

- **Project**: WSOP, HCL, GGMillions 등
- **HandClip**: 타임코드 기반 핸드 클립 (In/Out)
- **Tag**: poker_play, emotion, epic_hand, hand_grade 카테고리

## 버전 타입

| 타입 | 설명 | 파일명 특징 |
|------|------|------------|
| clean | 원본 클린 | `-clean`, `클린본` |
| mastered | 마스터링 완료 | Mastered 폴더 |
| stream | 풀 스트림 | STREAM 폴더 |
| subclip | 하이라이트 | SUBCLIP 폴더 |
