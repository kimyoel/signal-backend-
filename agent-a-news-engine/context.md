# context.md — 핵심 의사결정 기록

> 📌 이 파일의 목적
> "왜 이렇게 결정했는가"를 기록하는 파일입니다.
> AI 에이전트가 같은 질문을 반복하지 않도록, 기술 선택 근거와 방향 변경 이력을 남겨두는 문서입니다.

---

### 방향 변경: Hono 웹 대시보드 → Python 에이전트 A (2026-03-14)
- **변경 전**: Hono + Cloudflare Pages로 웹 대시보드를 먼저 만들려고 했음
- **변경 후**: 에이전트 A (Python + FastAPI) 코드 생성으로 변경
- **이유**: 요엘이 에이전트 A만 담당하라고 지시. 이 프로젝트의 범위는 뉴스 수집 + AI 분석 엔진

### 서버 프레임워크: FastAPI
- **결정**: FastAPI 사용
- **이유**: 비동기 지원 우수, 자동 문서 생성(Swagger), 설계서 원본 지정
- **탈락한 대안**: Flask (비동기 미지원), Django (너무 무거움)

### 스케줄러: APScheduler (AsyncIOScheduler)
- **결정**: APScheduler의 AsyncIOScheduler 사용
- **이유**: FastAPI의 이벤트 루프와 호환, 설계서 원본 지정
- **참고**: BackgroundScheduler가 아닌 AsyncIOScheduler — FastAPI가 asyncio 기반이므로

### DB 연동: supabase-py
- **결정**: supabase-py 공식 라이브러리 사용
- **이유**: 설계서 원본 지정, REST API 직접 호출보다 편리
- **주의**: Supabase 함수들이 동기 방식이라 async def 안에서 그대로 호출 (I/O 바운드라 실무적으로 문제없음)

### AI 모델 매핑 (현재 vs 설계서)
- **결정**: 현재 사용 가능한 모델로 매핑, 실제 배포 시 설계서 모델로 변경
- **매핑**:
  | 설계서 | 현재 코드 | 역할 |
  |--------|----------|------|
  | GPT-5.2 | gpt-4o | 매크로 분석 |
  | Gemini 3.1 Flash | gemini-2.0-flash | 데이터 분석 + 번역 |
  | Gemini 3.1 Flash-Lite | gemini-2.0-flash-lite | 뉴스 채점 |
  | Grok 4.1 | grok-3 | 소셜 센티먼트 |
  | Claude Haiku 4.5 | claude-haiku-4-5-20241022 | 환각 검증 |

### Grok API 호출 방식
- **결정**: httpx로 직접 REST 호출 (OpenAI 호환 형식)
- **이유**: xAI 공식 Python SDK가 아직 불안정, OpenAI 호환 API(https://api.x.ai/v1)가 더 안정적

### 배포: Railway (Docker)
- **결정**: Railway에 Dockerfile로 배포
- **이유**: 설계서 원본 지정, 24시간 상시 프로세스 지원, Git push 자동 배포

---

### 미결 사항
- [ ] Supabase 프로젝트 URL + API 키 — 요엘이 Supabase 대시보드에서 생성 필요
- [ ] AI API 키들 (OpenAI, Google, xAI, Anthropic) — 각 플랫폼에서 발급 필요
- [ ] NewsAPI 키 — newsapi.org에서 발급 필요
- [ ] Railway 프로젝트 생성 — railway.app에서 프로젝트 만들기
- [ ] 실제 모델명 업데이트 — GPT-5.2, Grok 4.1 출시 후 코드 변경
