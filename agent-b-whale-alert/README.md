# 🐋 SIGNAL — 에이전트 B (고래 알림 시스템)

> Whale Alert API로 대형 암호화폐 거래를 감지하고, 앱 사용자에게 푸시 알림을 발송하는 백엔드 엔진

---

## 역할

| 항목 | 내용 |
|------|------|
| **담당** | 온체인 대형 거래 감지 + 푸시 알림 발송 |
| **실행 주기** | 5분마다 자동 실행 |
| **배포** | Railway (Docker) |
| **DB** | Supabase — `whale_alerts` 테이블 |

## 기능

1. Whale Alert API에서 대형 거래 데이터 수집
2. 조건 충족 시 Supabase `whale_alerts` 테이블에 저장
3. Expo Push Notifications으로 앱 사용자에게 알림 발송

## 기술 스택

- Python 3.11+ / FastAPI / APScheduler
- Whale Alert API
- Expo Push Notifications
- Supabase (PostgreSQL)

## 상태

🔲 아직 개발 전
