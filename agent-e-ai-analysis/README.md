# SIGNAL — 에이전트 E (AI 3각도 분석 엔진)

## 프로젝트 개요
- **서비스**: SIGNAL 앱의 AI 분석 백엔드
- **역할**: 사용자가 "AI 분석 보기" 버튼 누르면 3개 AI가 동시에 분석해서 돌려주는 API
- **기술 스택**: Python + FastAPI + Supabase
- **배포 위치**: Railway

## 작동 원리 (쉽게 설명)
```
사용자가 "AI 분석" 버튼 클릭
         ↓
[1] 이미 분석한 뉴스? → 저장된 결과 바로 보여줌 (비용 0원)
[2] 처음 분석? → 3개 AI에게 동시에 질문
    📊 GPT-4o     → "경제적으로 이건 이런 의미야"
    🔗 Gemini     → "데이터를 보면 이런 패턴이야"
    📱 Grok       → "사람들 반응은 이래"
         ↓
[3] Claude가 검증 → "거짓 정보나 투자 권유 없는지 체크"
         ↓
[4] 결과 저장 + 사용자에게 반환
```

## API 엔드포인트
| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 서버 상태 확인 |
| GET | `/health` | 헬스체크 |
| POST | `/api/ai-analysis` | AI 3각도 분석 요청 |

### POST /api/ai-analysis
```json
// 요청
{
  "news_id": "뉴스 UUID",
  "models": ["gpt", "gemini", "grok"]
}

// 헤더
Authorization: Bearer {supabase_user_token}
```

## 파일 구조
```
webapp/
├── main.py                    # FastAPI 앱 시작점
├── app/
│   ├── config.py              # 환경변수 설정
│   ├── routes/
│   │   ├── health.py          # 헬스체크 API
│   │   └── analysis.py        # AI 분석 API (핵심)
│   ├── services/
│   │   ├── ai_clients.py      # GPT/Gemini/Grok/Claude 호출
│   │   ├── auth.py            # 인증 & 구독 확인
│   │   ├── cache.py           # 분석 결과 캐시
│   │   └── supabase_client.py # DB 연결
│   └── prompts/
│       └── templates.py       # AI 프롬프트 모음
├── tests/
│   └── test_analysis.py       # 테스트
├── requirements.txt           # Python 패키지 목록
├── .env.example               # 환경변수 템플릿
├── railway.json               # Railway 배포 설정
├── Procfile                   # 실행 명령
└── .gitignore                 # Git 제외 파일
```

## 환경변수 (.env 필요)
`.env.example`을 `.env`로 복사 후 실제 API 키 입력:
- `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`
- `OPENAI_API_KEY` (GPT용)
- `GOOGLE_API_KEY` (Gemini용)
- `XAI_API_KEY` (Grok용)
- `ANTHROPIC_API_KEY` (Claude 검증용)

## 현재 상태
- ✅ 프로젝트 구조 생성 완료
- ✅ FastAPI 앱 설정
- ✅ AI 3개 병렬 호출 로직
- ✅ Claude 할루시네이션 검증
- ✅ 캐시 시스템 (24시간 유효)
- ✅ 인증 & 크레딧 차감 로직
- ✅ Railway 배포 설정

## 다음 단계
- [ ] Supabase 프로젝트 연결 (API 키 설정)
- [ ] Railway 배포
- [ ] 실제 AI API 키 등록 & 테스트
- [ ] 에이전트 D(앱)와 연동 테스트
