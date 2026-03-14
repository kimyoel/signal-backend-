# ============================================
# 에이전트 E — AI 3각도 분석 엔진
# FastAPI 메인 앱 설정
# ============================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.analysis import router as analysis_router
from app.routes.health import router as health_router

app = FastAPI(
    title="SIGNAL Agent E — AI 분석 엔진",
    description="GPT + Gemini + Grok 3각도 병렬 분석 API",
    version="1.0.0",
)

# CORS 설정 (앱에서 API 호출할 수 있게)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 앱 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(health_router, tags=["Health"])
app.include_router(analysis_router, prefix="/api", tags=["AI Analysis"])
