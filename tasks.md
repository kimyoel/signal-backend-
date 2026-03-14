# tasks.md — 작업 체크리스트

---

## Phase 1 — MVP

### 프로젝트 셋업
- [x] plan.md 작성 (2026-03-14)
- [x] context.md 작성 (2026-03-14)
- [x] tasks.md 작성 (2026-03-14)
- [x] AGENT.md 프로젝트 루트에 배치 (2026-03-14)
- [x] .gitignore 생성 (2026-03-14)
- [x] requirements.txt 생성 (2026-03-14)
- [x] .env.example 생성 (2026-03-14)
- [x] Dockerfile 생성 (2026-03-14)

### 핵심 모듈 구현
- [x] config.py — 환경변수 + 상수 관리 (2026-03-14)
- [x] db.py — Supabase 연결 모듈 + 테스트 모드 지원 (2026-03-14)
- [x] whale_monitor.py — Whale Alert API 폴링 + 중복 체크 + DB 저장 (2026-03-14)
- [x] push_sender.py — Expo 푸시 알림 배치 발송 + 사용자 필터링 (2026-03-14)
- [x] main.py — APScheduler 엔트리포인트 (2026-03-14)

### 테스트
- [x] test_whale_monitor.py — 파싱/중복체크 테스트 8개 통과 (2026-03-14)
- [x] test_push_sender.py — 포맷/배치/필터링 테스트 11개 통과 (2026-03-14)

### 마무리
- [x] Git 초기화 + 첫 커밋 (2026-03-14)
- [x] 로컬 테스트 실행 확인 — 19개 전부 통과 (2026-03-14)
- [x] tasks.md 완료 항목 업데이트 (2026-03-14)

---

## Phase 2 — 안정화 (추후)
- [ ] cursor 관리 (마지막 처리 timestamp DB 저장)
- [ ] 무효 토큰 자동 정리 (DeviceNotRegistered)
- [ ] 에러 재시도 로직 (backoff)
- [ ] structlog 로깅 도입
- [ ] 헬스체크 엔드포인트

---

## 작업 로그

| 날짜 | 완료 항목 | 특이사항 |
|------|----------|---------|
| 2026-03-14 | Phase 1 MVP 전체 완료 | 에이전트 B 초기 구현 완료. 모든 핵심 모듈 + 테스트 19개 통과. db.py에 테스트 모드(TESTING 환경변수) 추가. context.md에 Supabase 키 검증 이슈 기록 필요. |

---

*마지막 업데이트: 2026-03-14*
