# tasks.md — 작업 체크리스트

> 📌 이 파일의 목적
> 개발 작업의 진행 상황을 추적하는 체크리스트 파일입니다.
> AI 에이전트가 새 세션을 열 때 "어디까지 했는지"를 즉시 파악하는 기준 문서입니다.
> 작업이 완료될 때마다 [ ] → [x] 로 바꿔주세요.

---

## Phase 1 — MVP (프로젝트 뼈대)

- [x] FastAPI 프로젝트 초기 구조 생성 (2026-03-14)
- [x] 환경변수 설정 파일 (config.py + .env.example) (2026-03-14)
- [x] 헬스체크 라우터 (health.py) (2026-03-14)
- [x] AI 분석 라우터 (analysis.py) (2026-03-14)
- [x] Supabase 클라이언트 서비스 (supabase_client.py) (2026-03-14)
- [x] 인증 + 크레딧 확인 서비스 (auth.py) (2026-03-14)
- [x] AI 클라이언트 서비스 — GPT/Gemini/Grok/Claude (ai_clients.py) (2026-03-14)
- [x] 캐시 서비스 (cache.py) (2026-03-14)
- [x] AI 프롬프트 상수 (prompts/templates.py) (2026-03-14)
- [x] Railway 배포 설정 (railway.json + Procfile) (2026-03-14)
- [x] Git 초기화 + .gitignore (2026-03-14)
- [x] AGENT.md / plan.md / context.md / tasks.md 작성 (2026-03-14)

## Phase 2 — 안정화

- [x] 에러 핸들링 강화 — 타임아웃 15초, 재시도 1회, 실패 격리 (2026-03-14)
- [x] 테스트 코드 작성 — retry + error_handling 18개 테스트 전부 통과 (2026-03-14)
- [x] 로깅 시스템 구축 (structured logging) — JSON 로거 + 전 서비스 적용, 32개 테스트 통과 (2026-03-14)
- [ ] Supabase 실제 연결 테스트
- [ ] GPT-4o API 실제 호출 테스트
- [ ] Gemini 1.5 Flash API 실제 호출 테스트
- [ ] Grok-2 API 실제 호출 테스트
- [ ] Claude Haiku 검증 실제 호출 테스트
- [ ] Railway 배포 + 실서버 테스트

## Phase 3 — 고도화

- [ ] 레이트 리밋 미들웨어 적용
- [ ] 분석 비용 추적 (generation_cost_usd 기록)
- [ ] 할루시네이션 로그 테이블 + 모니터링
- [ ] 프롬프트 버전 관리 시스템
- [ ] 에이전트 D(앱)와 통합 테스트

---

## 작업 로그

| 날짜 | 완료 항목 | 특이사항 |
|------|----------|---------|
| 2026-03-14 | Phase 1 전체 완료 | 프로젝트 뼈대 생성. 실제 API 키 미설정 상태. |
| 2026-03-14 | 관리 문서 4종 작성 | AGENT.md, plan.md, context.md, tasks.md |
| 2026-03-14 | 에러 핸들링 강화 | retry.py, errors.py 신규 생성. ai_clients.py, main.py, analysis.py 수정. 18개 테스트 통과. |
| 2026-03-14 | 로깅 시스템 구축 | logger.py 신규 생성. auth.py, cache.py, analysis.py, main.py, ai_clients.py에 로그 적용. test_logger.py 14개 테스트 추가. 총 32개 통과. |
