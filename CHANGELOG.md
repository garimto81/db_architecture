# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-12-09

### Added
- **HCL (Hustler Casino Live) Parser Support**
  - New regex pattern in `ParserAgent` for HCL/Hustler Casino Live video files
  - Supports year, season, episode, event_name, and part extraction
  - Comprehensive test coverage in `TestHCLParser` class

- **Block Rules Configuration Files** (`.block_rules`)
  - `BLOCK_PARSER`: 파일명 파싱 전담 에이전트 규칙
  - `BLOCK_SYNC`: 파일 동기화 전담 에이전트 규칙
  - `BLOCK_STORAGE`: 데이터베이스 저장 전담 에이전트 규칙
  - `BLOCK_QUERY`: 데이터 조회 전담 에이전트 규칙
  - `BLOCK_VALIDATION`: 데이터 검증 전담 에이전트 규칙
  - `BLOCK_EXPORT`: 데이터 내보내기 전담 에이전트 규칙

### Changed
- Updated `03_FILE_PARSER.md` LLD documentation with HCL Parser section (§2.6)
- Enhanced parametrized test cases to include HCL project detection

### Technical Details
- HCL regex pattern supports multiple naming conventions:
  - `HCL 2024 Episode 15 Part 2.mp4`
  - `Hustler Casino Live 2023 Poker Game.mp4`
  - `HCL_2024-03-15_High_Stakes.mp4`
  - `HCL Season 3 Episode 10.mp4`

## [1.0.0] - 2025-12-09

### Added
- **Block Agent System v1.0.0**
  - Core infrastructure: `BaseAgent`, `EventBus`, `CircuitBreaker`
  - 6 specialized Block Agents:
    - `ParserAgent` (BLOCK_PARSER): 파일명 파싱
    - `SyncAgent` (BLOCK_SYNC): NAS/GCS 파일 동기화
    - `StorageAgent` (BLOCK_STORAGE): SQLite 데이터 저장
    - `QueryAgent` (BLOCK_QUERY): 고급 검색 및 필터링
    - `ValidationAgent` (BLOCK_VALIDATION): 데이터 무결성 검증
    - `ExportAgent` (BLOCK_EXPORT): CSV/JSON/JSONL 내보내기
  - `OrchestratorAgent`: YAML 기반 워크플로우 실행
  - `WorkflowParser`: 워크플로우 정의 파싱

- **Documentation**
  - PRD v5.1: 제품 요구사항 문서
  - Architecture Design: 블럭 에이전트 시스템 아키텍처
  - LLD Documents:
    - `01_DATABASE_SCHEMA.md`: 데이터베이스 스키마
    - `02_SYNC_SYSTEM.md`: 동기화 시스템
    - `03_FILE_PARSER.md`: 파일 파서
    - `04_DOCKER_DEPLOYMENT.md`: Docker 배포
    - `05_AGENT_SYSTEM.md`: 에이전트 시스템

- **Workflow Definitions**
  - `nas_sync.yaml`: NAS 동기화 워크플로우

### Features
- Token budget management per block (30K-55K limits)
- Circuit Breaker pattern for fault isolation
- EventBus Pub/Sub for inter-block communication
- Scope validation with `.block_rules` YAML configuration
- Variable interpolation in workflows (`${step_id.output}`)
