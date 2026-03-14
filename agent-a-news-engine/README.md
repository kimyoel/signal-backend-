# Agent A — News Engine

> SIGNAL 뉴스 수집 + AI 분석 에이전트

## 개요
- 30분마다 RSS/NewsAPI에서 글로벌 투자 뉴스 수집
- Google Gemini로 중요도 스코어링 (1~5)
- 한국어 번역 + DB 저장
- 중요도 5 뉴스 → Agent C (Threads 자동 포스팅) 트리거

## 상태
- [ ] 미구현 — 추후 개발 예정

## 참고 문서
- `00_master_architecture.md`
- `01_db_schema.md`
- `02_agent_a_news_engine.md`
