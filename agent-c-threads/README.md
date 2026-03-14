# 📣 SIGNAL — 에이전트 C (Threads 자동 포스팅)

> 중요도 5 뉴스를 감지해서 Threads에 자동으로 포스팅하는 마케팅 엔진

---

## 역할

| 항목 | 내용 |
|------|------|
| **담당** | 중요도 5 뉴스 감지 → Threads 자동 포스팅 |
| **실행 방식** | 이벤트 트리거 (뉴스 저장 후 폴링) |
| **배포** | Railway (Docker) |
| **DB** | Supabase — `news` 테이블 (`posted_to_threads` 컬럼) |

## 기능

1. `news` 테이블에서 `importance=5 AND posted_to_threads=false` 폴링
2. Threads API로 자동 포스팅
3. 포스팅 후 `posted_to_threads=true`로 업데이트

## 기술 스택

- Python 3.11+ / FastAPI / APScheduler
- Threads API (Meta)
- Supabase (PostgreSQL)

## 상태

🔲 아직 개발 전
