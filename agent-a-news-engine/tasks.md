# tasks.md — 작업 체크리스트

> 📌 이 파일의 목적
> 개발 작업의 진행 상황을 추적하는 체크리스트 파일입니다.
> AI 에이전트가 새 세션을 열 때 "어디까지 했는지"를 즉시 파악하는 기준 문서입니다.

---

## Phase 1 — 코드 뼈대

### 초기 세팅
- [x] 기존 Hono 프로젝트 삭제 (2026-03-14)
- [x] Python 프로젝트 구조 생성 (2026-03-14)
- [x] 관리 파일 배치 — AGENT.md, plan.md, context.md, tasks.md (2026-03-14)
- [x] .gitignore + .env.example + requirements.txt + Dockerfile (2026-03-14)

### Python 소스 파일
- [x] prompts.py — AI 프롬프트 6개 (채점, 번역, GPT, Gemini, Grok, Claude) (2026-03-14)
- [x] db.py — Supabase 연결 + 쿼리 함수 10개 (2026-03-14)
- [x] sources.py — RSS 소스 로드 + NewsAPI 키워드 (2026-03-14)
- [x] collector.py — 뉴스 수집 파이프라인 전체 (6단계) (2026-03-14)
- [x] analyzer.py — AI 3각 분석 엔진 전체 (7단계) (2026-03-14)
- [x] main.py — FastAPI + APScheduler 통합 (2026-03-14)

### git
- [x] git init + 초기 커밋 (2026-03-14)

---

## Phase 2 — 검증 + 배포 준비

- [x] Python lint 체크 (pyflakes) — 에러 0개 (2026-03-14)
- [x] Railway 배포 가이드 작성 (2026-03-14)
- [x] README.md 작성 (2026-03-14)

---

## Phase 3 — 고도화 (향후)

- [ ] 에러 핸들링 강화 (재시도 로직, exponential backoff)
- [ ] AI 비용 모니터링 (generation_cost_usd 기록)
- [ ] /collect 엔드포인트 인증 추가
- [ ] 수집 통계 로깅
- [ ] 테스트 코드 작성 (pytest)

---

## 작업 로그

| 날짜 | 완료 항목 | 특이사항 |
|------|----------|---------|
| 2026-03-14 | 기존 Hono 삭제 + Python 에이전트 A 전체 구조 생성 | 6개 .py 파일 + 설정 파일 + 관리 파일 4종 |
| 2026-03-14 | Python lint 통과 (pyflakes 에러 0) + README.md 작성 | Railway 배포 가이드 포함 |
| 2026-03-14 | GitHub push 완료 — signal-backend 모노레포 구조 (A/B/C/E) | kimyoel/signal-backend- |
