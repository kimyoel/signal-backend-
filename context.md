# context.md — 핵심 의사결정 기록

---

### Python 3.11+ 선택
- **결정**: Python 사용
- **이유**: 마스터 설계서(00_master_architecture.md)에서 백엔드 자동화 언어로 Python + APScheduler를 지정함. 에이전트 A, B, C 모두 Python으로 통일되어 있어 코드 재사용과 유지보수에 유리
- **탈락한 대안**: Node.js (설계서에서 Python으로 결정됨, 변경 이유 없음)

### APScheduler 선택
- **결정**: APScheduler 3.10 사용
- **이유**: 5분 주기 반복 실행에 최적. cron보다 Python 코드 내에서 관리하기 쉽고, Railway에서 별도 cron 설정 없이 돌릴 수 있음
- **탈락한 대안**: Celery (오버스펙 — Redis 등 추가 인프라 필요), Railway Cron (세밀한 에러 핸들링 어려움)

### httpx 선택
- **결정**: httpx 0.27 사용
- **이유**: 에이전트 B 스펙 문서에서 지정. async 지원이 좋아서 Whale Alert API와 Expo Push API를 비동기로 호출 가능. requests보다 현대적
- **탈락한 대안**: requests (동기 전용, async 미지원), aiohttp (API가 복잡)

### supabase-py 선택
- **결정**: supabase-py 2.7 사용
- **이유**: Supabase 공식 Python SDK. REST API 직접 호출보다 편하고, 인증/RLS를 service_role_key로 우회 가능
- **탈락한 대안**: psycopg2로 직접 PostgreSQL 연결 (Supabase REST API 활용이 더 간편)

### Expo Push Notifications 선택
- **결정**: Expo Push API 직접 호출
- **이유**: 마스터 설계서에서 앱이 React Native + Expo 기반. Expo Push가 자연스러운 선택. OneSignal에서 Expo Push로 변경됨 (마스터 설계서 8-3 참고)
- **참고**: 마스터 설계서 데이터 흐름에서는 OneSignal이라고 되어 있으나, 실제 스펙(03 문서)에서는 Expo Push로 확정

### Railway 배포
- **결정**: Railway에서 Docker 컨테이너로 24시간 실행
- **이유**: 마스터 설계서에서 배포 플랫폼으로 Railway 지정. APScheduler가 상시 돌아야 하므로 서버리스(Cloudflare 등)는 부적합
- **탈락한 대안**: Cloudflare Workers (Python 미지원, 상시 실행 불가), Heroku (비용)

### DB 테스트 모드 도입 (2026-03-14)
- **결정**: db.py에 TESTING 환경변수로 테스트 모드 분기 추가
- **이유**: supabase-py 2.7은 create_client() 시점에 API 키 형식을 검증함. 테스트에서 가짜 키로는 클라이언트 생성 자체가 실패. TESTING=true일 때 supabase 객체를 None으로 두고 테스트에서 mock 처리하는 방식 채택
- **탈락한 대안**: monkeypatch로 create_client mock (import 순서 이슈로 복잡), 실제 Supabase 프로젝트로 테스트 (비용, 외부 의존)

---

### _ChainableMock 테스트 헬퍼 도입 (2026-03-14)
- **결정**: Supabase 쿼리 체이닝용 커스텀 Mock 클래스 작성
- **이유**: Supabase SDK의 `.not_.is_()` 패턴은 속성 접근(.not_)과 메서드 호출(.is_())이 혼합됨. 일반 MagicMock은 이 패턴을 제대로 처리 못함 — `.not_` 접근 시 MagicMock 자동 생성되지만 그 위에 `.is_()` 호출이 체이닝되지 않음. `_ChainableMock`은 `__getattr__`로 self 반환 + `__call__`로 self 반환하여, 어떤 체이닝 패턴이든 최종 `.execute()`에서 미리 지정한 결과를 돌려줌
- **탈락한 대안**: MagicMock의 return_value 체이닝 (`.not_.return_value.is_.return_value...` — 깊이가 깊으면 깨짐), monkeypatch로 select 함수 자체 교체 (코드 결합도 높아짐)

### 동기(sync) 방식 유지 결정 (2026-03-14)
- **결정**: httpx를 동기 모드로 사용 (httpx.post/get)
- **이유**: 03 스펙 문서에서는 async를 예시로 들었으나, APScheduler의 BlockingScheduler가 동기 실행 기반. 비동기로 전환하려면 AsyncScheduler + asyncio 이벤트 루프 관리 필요 → MVP에서는 오버엔지니어링. 5분 간격이라 동시성 이슈도 없음
- **탈락한 대안**: httpx.AsyncClient + AsyncScheduler (복잡도 증가, 실익 적음)
- **향후**: Phase 2에서 병렬 푸시 발송이 필요하면 그때 비동기 전환 검토

### 미결 사항
- [ ] cursor 관리 방식: 로컬 파일 vs Supabase 테이블 (Phase 2에서 결정)
- [ ] 푸시 알림 실패 시 재시도 횟수 (Phase 2에서 결정)

---

*마지막 업데이트: 2026-03-14 (검토 지적사항 수정 후)*
