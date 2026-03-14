# Agent C — Threads Auto-Posting

> SIGNAL Threads 자동 포스팅 에이전트

## 개요
- 중요도 5 뉴스 감지 시 Threads에 자동 포스팅
- `news` 테이블에서 `importance=5 AND posted_to_threads=false` 폴링
- Threads API로 포스트 생성

## 상태
- [ ] 미구현 — 추후 개발 예정

## 참고 문서
- `00_master_architecture.md`
- `01_db_schema.md`
- `04_agent_c_threads.md`
