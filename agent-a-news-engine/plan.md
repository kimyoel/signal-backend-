# plan.md — 전체 설계 및 개발 계획

> 📌 이 파일의 목적
> 프로젝트의 전체 구조와 단계별 개발 계획을 기록하는 파일입니다.
> AI 에이전트가 새 세션을 시작할 때 "이 프로젝트가 뭔지"를 파악하는 핵심 문서입니다.

---

## 서비스 한 줄 소개

**SIGNAL 에이전트 A** — 전 세계 투자 뉴스를 자동 수집·채점·번역하고, 사용자 요청 시 AI 3각 분석을 실행하는 백엔드 엔진

---

## 시스템 내 위치

```
이 프로젝트 → 에이전트 A (뉴스수집 + AI분석)
                    ↕
              Supabase (공통 DB)
                    ↕
          에이전트 D (앱) — 사용자가 분석 요청
          에이전트 C (Threads) — 중요도 5 감지
```

---

## 기술 스택

| 항목 | 기술 | 역할 |
|------|------|------|
| 언어 | Python 3.11+ | 메인 언어 |
| 서버 | FastAPI + Uvicorn | API 엔드포인트 |
| 스케줄러 | APScheduler (AsyncIOScheduler) | 30분마다 뉴스 수집 자동 실행 |
| HTTP | httpx (비동기) | RSS 피드, NewsAPI, Grok API 호출 |
| RSS | feedparser | RSS XML 파싱 |
| DB | supabase-py | Supabase(PostgreSQL) 연동 |
| AI | openai (GPT) | 매크로 경제 분석 |
| AI | google-generativeai (Gemini) | 뉴스 채점/번역/데이터 분석 |
| AI | httpx (Grok API) | 소셜 센티먼트 분석 |
| AI | anthropic (Claude) | 환각 검증 |
| 배포 | Railway (Docker) | 24시간 상시 실행 |

---

## 파일 구조

```
webapp/
├── main.py              # 진입점 — FastAPI + APScheduler
├── collector.py         # 뉴스 수집 파이프라인 (30분마다)
├── analyzer.py          # AI 3각 분석 엔진 (요청 시)
├── sources.py           # RSS 소스 목록 + NewsAPI 키워드
├── prompts.py           # AI 프롬프트 6개 모음
├── db.py                # Supabase 연결 + 쿼리 함수 모음
├── requirements.txt     # Python 패키지 목록
├── Dockerfile           # Railway 배포용 Docker 설정
├── .env.example         # 환경변수 예시
├── .gitignore           # Python용 gitignore
├── AGENT.md             # AI 에이전트 규칙서
├── plan.md              # 이 파일
├── context.md           # 기술 결정 기록
└── tasks.md             # 작업 체크리스트
```

---

## 담당 기능 2가지

### 기능 1 — 자동 뉴스 수집 파이프라인 (collector.py)
> 30분마다 APScheduler가 자동 실행

1. Supabase `analyst_sources` 테이블에서 활성 소스 로드
2. RSS 피드 + NewsAPI 병렬 수집
3. `source_url` 기준 중복 제거
4. Gemini Flash-Lite로 중요도 1~5 채점
5. 중요도 3 미만 버림
6. Gemini Flash로 한국어 번역 + 요약
7. `news` 테이블에 저장
8. 중요도 5 → `posted_to_threads=false` (에이전트 C용)

### 기능 2 — On-Demand AI 3각 분석 (analyzer.py)
> 앱에서 POST /analyze 호출 시 실행

1. `ai_analyses` 캐시 확인
2. 사용자 크레딧 확인 (0이면 거절)
3. GPT + Gemini + Grok 병렬 호출 (asyncio.gather)
4. Claude Haiku 검증 (PASS/FAIL)
5. `ai_analyses` 테이블에 저장
6. 크레딧 차감
7. 결과 반환

---

## API 엔드포인트

| 메서드 | 경로 | 역할 |
|--------|------|------|
| GET | `/` | 헬스 체크 |
| POST | `/analyze` | AI 3각 분석 요청 (news_id, user_id) |
| POST | `/collect` | 수동 뉴스 수집 트리거 (관리용) |
| GET | `/status` | 스케줄러 상태 확인 |

---

## Phase별 개발 계획

### Phase 1 — 코드 뼈대 (현재)
- [x] 프로젝트 구조 생성
- [x] 모든 .py 파일 뼈대 + 함수 구현

### Phase 2 — 검증 + 배포
- [ ] Python lint 체크 + 문법 검증
- [ ] Railway 배포 가이드 작성
- [ ] README.md 작성

### Phase 3 — 고도화 (향후)
- [ ] 에러 핸들링 강화 (재시도 로직)
- [ ] AI 비용 모니터링 (generation_cost_usd 기록)
- [ ] 수집 통계 대시보드
