# tasks.md — 작업 체크리스트

---

## Phase 1 — MVP

### 프로젝트 셋업
- [ ] plan.md 작성
- [ ] context.md 작성
- [ ] tasks.md 작성
- [ ] AGENT.md 프로젝트 루트에 배치
- [ ] .gitignore 생성
- [ ] requirements.txt 생성
- [ ] .env.example 생성
- [ ] Dockerfile 생성

### 핵심 모듈 구현
- [ ] config.py — 환경변수 + 상수 관리
- [ ] db.py — Supabase 연결 모듈 (검토/수정)
- [ ] whale_monitor.py — Whale Alert API 폴링 + 중복 체크 + DB 저장
- [ ] push_sender.py — Expo 푸시 알림 배치 발송 + 사용자 필터링
- [ ] main.py — APScheduler 엔트리포인트

### 테스트
- [ ] test_whale_monitor.py — 폴링/파싱/중복체크 테스트
- [ ] test_push_sender.py — 알림 포맷/배치 로직 테스트

### 마무리
- [ ] Git 초기화 + 첫 커밋
- [ ] 로컬 테스트 실행 확인 (구조적 실행)
- [ ] tasks.md 완료 항목 업데이트

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
| 2026-03-14 | 프로젝트 시작 | 마스터 설계서 기반으로 에이전트 B 개발 착수 |

---

*마지막 업데이트: 2026-03-14*
