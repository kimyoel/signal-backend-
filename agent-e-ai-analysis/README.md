# 🧠 SIGNAL — 에이전트 E (AI 분석 서비스)

> 향후 확장용 AI 분석 전용 서비스 모듈

---

## 역할

| 항목 | 내용 |
|------|------|
| **담당** | AI 분석 기능의 독립 서비스화 (에이전트 A에서 분리 예정) |
| **실행 방식** | API 호출 시 실행 |
| **배포** | Railway (Docker) |
| **DB** | Supabase — `ai_analyses` 테이블 |

## 배경

현재 AI 3각 분석 기능은 에이전트 A(`analyzer.py`)에 포함되어 있음.
트래픽이 증가하면 분석 기능을 독립 서비스로 분리하여 스케일링할 수 있도록 이 폴더를 예약.

## 향후 계획

1. 에이전트 A의 `analyzer.py` 로직을 이 서비스로 이전
2. GPT / Gemini / Grok 호출을 독립 워커로 분리
3. 분석 큐 시스템 도입 (요청 → 큐 → 처리 → 결과 반환)

## 기술 스택

- Python 3.11+ / FastAPI
- OpenAI, Google AI, xAI, Anthropic API
- Supabase (PostgreSQL)

## 상태

🔲 아직 개발 전 (에이전트 A에서 분리 예정)
