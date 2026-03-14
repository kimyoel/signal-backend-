# 📡 SIGNAL — 에이전트 A (뉴스 수집 + AI 분석 엔진)

> 전 세계 투자 뉴스를 자동 수집·채점·번역하고, 사용자 요청 시 AI 3각 분석을 실행하는 백엔드 엔진

---

## 한눈에 보기

| 항목 | 내용 |
|------|------|
| **역할** | SIGNAL 시스템의 뉴스 수집 + AI 분석 담당 |
| **기술** | Python 3.11 + FastAPI + APScheduler |
| **배포** | Railway (Docker) |
| **DB** | Supabase (PostgreSQL) |
| **AI** | GPT + Gemini + Grok + Claude |

---

## 프로젝트 구조

```
webapp/
├── main.py              # 진입점 — FastAPI 서버 + APScheduler
├── collector.py         # 뉴스 수집 파이프라인 (30분마다 자동)
├── analyzer.py          # AI 3각 분석 엔진 (요청 시)
├── sources.py           # RSS 소스 목록 + NewsAPI 키워드
├── prompts.py           # AI 프롬프트 6개 모음
├── db.py                # Supabase 연결 + 쿼리 함수
├── requirements.txt     # Python 패키지 목록
├── Dockerfile           # Railway 배포용
├── .env.example         # 환경변수 템플릿
└── .gitignore
```

---

## 기능 2가지

### 기능 1 — 자동 뉴스 수집 (30분마다)

```
RSS 피드 + NewsAPI 수집
    → 중복 제거 (source_url 기준)
    → Gemini Flash-Lite로 중요도 1~5 채점
    → 중요도 3 미만 버림
    → Gemini Flash로 한국어 번역 + 요약
    → Supabase news 테이블 저장
    → 중요도 5는 에이전트 C(Threads)에 전달
```

### 기능 2 — AI 3각 분석 (요청 시)

```
POST /analyze 요청 수신
    → 캐시 확인 (이미 분석했으면 바로 반환)
    → 크레딧 확인 (0이면 거절)
    → GPT + Gemini + Grok 병렬 호출
    → Claude Haiku 환각 검증
    → 결과 저장 + 크레딧 차감
    → 결과 반환
```

---

## API 엔드포인트

| 메서드 | 경로 | 역할 |
|--------|------|------|
| `GET` | `/` | 헬스 체크 (서버 상태 확인) |
| `POST` | `/analyze` | AI 3각 분석 요청 |
| `POST` | `/collect` | 수동 뉴스 수집 트리거 |
| `GET` | `/status` | 스케줄러 상태 확인 |

### POST /analyze 요청/응답

```json
// 요청
{
  "news_id": "뉴스 UUID",
  "user_id": "사용자 UUID"
}

// 응답 (성공)
{
  "success": true,
  "gpt_analysis": "매크로 분석 결과...",
  "gemini_analysis": "데이터 분석 결과...",
  "grok_analysis": "소셜 분석 결과...",
  "verified": true
}

// 응답 (크레딧 부족)
{
  "success": false,
  "error": "insufficient_credits",
  "message": "AI 분석 이용권이 부족합니다."
}
```

---

## 로컬 실행 방법

### 1. 환경 준비

```bash
# Python 3.11+ 필요
python --version

# 가상환경 만들기
python -m venv .venv
source .venv/bin/activate   # Mac/Linux
# .venv\Scripts\activate    # Windows

# 패키지 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
# .env.example을 복사해서 .env 만들기
cp .env.example .env

# .env 파일 열어서 실제 키 채우기
# 필수: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
# 필수: OPENAI_API_KEY, GOOGLE_AI_API_KEY, XAI_API_KEY, ANTHROPIC_API_KEY
# 필수: NEWSAPI_KEY
```

### 3. 서버 실행

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 서버가 뜨면:
# - http://localhost:8000       → 헬스 체크
# - http://localhost:8000/docs  → API 문서 (Swagger)
# - 자동으로 첫 뉴스 수집 시작됨 (30분 간격)
```

---

## Railway 배포 방법

### 1단계: Railway 프로젝트 생성

1. [railway.app](https://railway.app) 접속 → 로그인
2. **New Project** → **Deploy from GitHub repo** 선택
3. 이 저장소 연결

### 2단계: 환경변수 설정

Railway 대시보드 → Variables 탭에서 아래 환경변수 추가:

```
SUPABASE_URL=https://프로젝트ID.supabase.co
SUPABASE_SERVICE_ROLE_KEY=서비스롤키
OPENAI_API_KEY=sk-xxxx
GOOGLE_AI_API_KEY=구글AI키
XAI_API_KEY=xAI키
ANTHROPIC_API_KEY=sk-ant-xxxx
NEWSAPI_KEY=뉴스API키
PORT=8000
```

### 3단계: 배포

- Railway가 Dockerfile을 감지해서 자동 빌드·배포
- Git push하면 자동 재배포

### 4단계: 확인

```bash
# Railway가 부여한 URL로 확인
curl https://your-app.railway.app/
curl https://your-app.railway.app/status
```

---

## 필요한 외부 서비스 & API 키

| 서비스 | 발급 URL | 환경변수명 |
|--------|---------|-----------|
| Supabase | [supabase.com](https://supabase.com) | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| OpenAI | [platform.openai.com](https://platform.openai.com) | `OPENAI_API_KEY` |
| Google AI | [aistudio.google.com](https://aistudio.google.com) | `GOOGLE_AI_API_KEY` |
| xAI (Grok) | [x.ai/api](https://x.ai/api) | `XAI_API_KEY` |
| Anthropic | [console.anthropic.com](https://console.anthropic.com) | `ANTHROPIC_API_KEY` |
| NewsAPI | [newsapi.org](https://newsapi.org) | `NEWSAPI_KEY` |

---

## Supabase DB 테이블 (에이전트 A가 사용하는 것)

| 테이블 | 역할 | 읽기/쓰기 |
|--------|------|----------|
| `analyst_sources` | RSS 소스 목록 | 읽기 |
| `news` | 수집된 뉴스 저장 | 읽기+쓰기 |
| `ai_analyses` | AI 분석 결과 캐시 | 읽기+쓰기 |
| `users` | 크레딧 조회/차감 | 읽기+쓰기 |

> DB 스키마 상세는 `01_db_schema.md` 참고

---

## 주의사항

1. **캐시 활용** — 같은 뉴스에 AI를 두 번 호출하지 않음 (ai_analyses 먼저 확인)
2. **병렬 처리** — GPT + Gemini + Grok은 asyncio.gather로 동시 호출
3. **에러 허용** — 3개 AI 중 하나 실패해도 나머지 2개는 반환
4. **면책 고지** — 모든 AI 분석 결과에 투자 면책 고지 필수
5. **API 키 보호** — 절대 코드에 직접 쓰지 않고 환경변수만 사용
