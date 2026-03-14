# Agent B — Whale Alert

> SIGNAL 대형 거래(고래) 감지 + 푸시 알림 에이전트

## 개요
- 5분마다 Whale Alert API 폴링
- $100만 이상 대형 거래 감지 및 Supabase DB 저장
- 구독 등급별 Expo 푸시 알림 발송 (FREE: $500만+, BASIC/PRO: $100만+)
- 미발송 건 자동 재시도

## 현재 상태
- [x] Phase 1 MVP 완료 (2026-03-14)
- [x] 코드 검토 수정 완료 — 테스트 40개 통과

## 파일 구조
```
agent-b-whale-alert/
├── config.py          # 환경변수 + 상수 관리
├── db.py              # Supabase 연결
├── whale_monitor.py   # API 폴링 + 중복체크 + DB 저장
├── push_sender.py     # Expo 푸시 배치 발송
├── main.py            # APScheduler 엔트리포인트
├── requirements.txt   # Python 의존성
├── Dockerfile         # Railway 배포용
├── .env.example       # 환경변수 템플릿
└── tests/             # 테스트 (40개)
```

## 기술 스택
Python 3.11+ / APScheduler / httpx / supabase-py / Expo Push API

## 배포
Railway에서 Docker 컨테이너로 24시간 실행

## 참고 문서
- `00_master_architecture.md`
- `01_db_schema.md`
- `03_agent_b_whale_alert.md`
