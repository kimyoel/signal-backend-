# plan.md — 전체 설계 및 개발 계획

> 📌 이 파일의 목적
> 프로젝트의 전체 구조와 단계별 개발 계획을 기록하는 파일입니다.
> AI 에이전트가 새 세션을 시작할 때 "이 프로젝트가 뭔지"를 파악하는 핵심 문서입니다.
> 계획이 바뀔 때마다 이 파일을 업데이트하세요.

---

## 한 줄 소개
SIGNAL 앱의 **에이전트 E** — 사용자가 뉴스에서 "AI 분석 보기" 버튼을 누르면, GPT(매크로) + Gemini(데이터/온체인) + Grok(소셜 심리) 3개 AI를 동시에 호출하여 3각도 분석을 반환하는 온디맨드 API 서버

## 기술 스택
| 항목 | 기술 | 역할 |
|------|------|------|
| 언어 | Python 3.11+ | 서버 로직 |
| 웹 프레임워크 | FastAPI | REST API 서버 |
| 병렬 처리 | asyncio + aiohttp | 3개 AI 동시 호출 |
| AI — 매크로 분석 | OpenAI GPT-4o | 거시경제 관점 분석 |
| AI — 데이터 분석 | Google Gemini 1.5 Flash | 온체인/데이터 관점 분석 |
| AI — 소셜 분석 | xAI Grok-2 | 소셜 심리 관점 분석 |
| AI — 검증 | Anthropic Claude 3 Haiku | 할루시네이션 + 금지표현 필터 |
| DB | Supabase (PostgreSQL) | 뉴스/분석/유저 데이터 |
| 캐시 | Supabase ai_analyses 테이블 | 24시간 캐시 (비용 절감) |
| 배포 | Railway | 24시간 상시 운영 |

## 전체 디렉토리 구조
```
webapp/
├── AGENT.md                   # AI 에이전트 규칙서
├── plan.md                    # 이 파일 (전체 설계)
├── context.md                 # 의사결정 기록
├── tasks.md                   # 작업 체크리스트
├── main.py                    # FastAPI 앱 시작점
├── app/
│   ├── config.py              # 환경변수 설정 (pydantic-settings)
│   ├── routes/
│   │   ├── health.py          # GET / , GET /health
│   │   └── analysis.py        # POST /api/ai-analysis (핵심)
│   ├── services/
│   │   ├── ai_clients.py      # GPT/Gemini/Grok/Claude 호출 로직
│   │   ├── auth.py            # Supabase JWT 검증 + 크레딧 확인
│   │   ├── cache.py           # 분석 결과 캐시 (24h TTL)
│   │   └── supabase_client.py # Supabase 클라이언트 싱글톤
│   └── prompts/
│       └── templates.py       # 4개 AI 프롬프트 상수
├── tests/                     # 테스트 코드
├── requirements.txt           # Python 의존성
├── .env.example               # 환경변수 템플릿
├── railway.json               # Railway 배포 설정
├── Procfile                   # 실행 명령
└── .gitignore
```

## 핵심 API 엔드포인트
| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| GET | `/` | 없음 | 서버 상태 확인 |
| GET | `/health` | 없음 | 헬스체크 (Railway용) |
| POST | `/api/ai-analysis` | Bearer Token | AI 3각도 분석 요청 |

## Phase별 개발 계획

### Phase 1 — MVP (현재)
프로젝트 뼈대 + 핵심 API 로직 구현
- FastAPI 프로젝트 구조 생성 ✅
- AI 3개 병렬 호출 로직 ✅
- Claude 할루시네이션 검증 ✅
- 캐시 시스템 ✅
- 인증 + 크레딧 차감 ✅
- Railway 배포 설정 ✅

### Phase 2 — 안정화
실제 API 연동 테스트 + 에러 핸들링 강화
- Supabase 실제 연결 테스트
- 각 AI API 실제 호출 테스트
- 에러 핸들링 & 타임아웃 처리
- 로깅 시스템 구축
- 테스트 코드 작성

### Phase 3 — 고도화
성능 최적화 + 모니터링
- 레이트 리밋 적용
- 비용 모니터링 (분석 1회당 비용 추적)
- 할루시네이션 로그 & 프롬프트 개선 사이클
- 에이전트 D(앱)와 통합 테스트

## 개발 원칙
1. **비용 최소화**: 캐시 히트율 70%+ 목표 (같은 뉴스 → 재호출 안 함)
2. **법적 안전**: 모든 응답에 면책 고지 필수, 투자 권유 표현 자동 필터링
3. **병렬 우선**: 3개 AI는 항상 동시 호출 (순차 X)
4. **실패 격리**: 1개 AI가 실패해도 나머지 2개 결과는 정상 반환
