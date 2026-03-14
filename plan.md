# plan.md — 전체 설계 및 개발 계획

---

## 프로젝트 한 줄 소개

**SIGNAL 에이전트 B** — 5분마다 Whale Alert API를 감시해서 대형 온체인 거래를 감지하고, Supabase에 저장 + 앱 사용자에게 Expo 푸시 알림을 보내는 Python 백엔드 서비스

---

## 기술 스택

| 레이어 | 기술 | 역할 |
|--------|------|------|
| 언어 | Python 3.11+ | 메인 런타임 |
| 스케줄러 | APScheduler 3.10 | 5분 주기 자동 실행 |
| HTTP 클라이언트 | httpx 0.27 | Whale Alert API 호출 + Expo Push API 호출 |
| DB 클라이언트 | supabase-py 2.7 | Supabase(PostgreSQL) 읽기/쓰기 |
| 환경변수 | python-dotenv 1.0 | .env 파일에서 비밀키 로드 |
| 배포 | Railway (Docker) | 24시간 상시 실행 |
| 푸시 알림 | Expo Push Notifications API | 앱 사용자에게 알림 발송 |
| 외부 API | Whale Alert API (v1) | 온체인 대형 거래 데이터 소스 |

---

## 디렉토리 구조

```
signal-backend/
├── AGENT.md                    # AI 에이전트 규칙서
├── plan.md                     # 이 파일 (전체 설계)
├── context.md                  # 기술 결정 기록
├── tasks.md                    # 작업 체크리스트
├── .gitignore
│
├── agent-a-news-engine/        # 에이전트 A — 뉴스 수집 + AI 분석 (미구현)
│   └── README.md
│
├── agent-b-whale-alert/        # 에이전트 B — 고래 감지 + 푸시 알림 ✅
│   ├── main.py
│   ├── whale_monitor.py
│   ├── push_sender.py
│   ├── db.py
│   ├── config.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── README.md
│   └── tests/
│       ├── test_whale_monitor.py
│       └── test_push_sender.py
│
├── agent-c-threads/            # 에이전트 C — Threads 자동 포스팅 (미구현)
│   └── README.md
│
└── agent-e-ai-analysis/        # 에이전트 E — AI 3각 분석 (미구현)
    └── README.md
```

---

## Phase별 개발 계획

### Phase 1 — MVP (현재)
> 핵심 기능만 동작하는 최소 버전

- Whale Alert API 폴링 (5분 주기)
- tx_hash 기반 중복 제거
- Supabase whale_alerts 테이블에 저장
- Expo 푸시 알림 배치 발송
- FREE/BASIC/PRO 사용자별 알림 필터링
- Docker + Railway 배포 가능 상태

### Phase 2 — 안정화 (Phase 1 완료 후)
- cursor 관리 (마지막 처리 timestamp DB 저장)
- 무효 토큰(DeviceNotRegistered) 자동 정리
- 에러 재시도 로직 (API 실패 시 backoff)
- 로깅 고도화 (structlog 도입)
- 헬스체크 엔드포인트 추가

### Phase 3 — 고도화 (추후)
- 알림 집계 (동일 코인 단기간 대량 이동 시 묶어서 알림)
- 시세 연동 (가격 변동률 같이 표시)
- 통계 대시보드 데이터 제공

---

## 핵심 외부 API

### Whale Alert API
- **엔드포인트**: `GET https://api.whale-alert.io/v1/transactions`
- **파라미터**: `min_value=1000000`, `api_key`, `cursor`
- **제한**: 무료 플랜 분당 10 요청 (5분 간격이면 충분)

### Expo Push API
- **엔드포인트**: `POST https://exp.host/--/api/v2/push/send`
- **배치**: 최대 100개씩 묶어서 발송
- **인증**: Bearer 토큰 (EXPO_ACCESS_TOKEN)

---

## 개발 원칙

1. **환경변수 필수** — API 키, DB 정보는 절대 코드에 하드코딩 하지 않음
2. **중복 방지 최우선** — tx_hash + whale_alert_id로 이중 중복 체크
3. **실패 허용** — API 1회 실패해도 다음 5분 주기에 자동 재시도
4. **한국어 주석** — IT 비전공자도 읽을 수 있도록 주석 충실히 작성
5. **한 기능 한 파일** — 파일별 역할 명확히 분리

---

*마지막 업데이트: 2026-03-14*
