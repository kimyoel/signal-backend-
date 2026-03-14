# ============================================
# 에이전트 E — AI 3각도 분석 엔진
# FastAPI 메인 앱 설정
# ============================================
# [v1.1] 전역 예외 핸들러 추가
# - 모든 에러가 일관된 JSON 형식으로 반환됨
# - 예상 못한 에러도 500 JSON으로 처리 (서버 크래시 방지)
#
# [v1.2] 로깅 시스템 통합
# - 서버 시작 시 setup_logging() 호출
# - 전역 에러 핸들러에 에러 로그 추가
# ============================================

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.errors import SignalBaseError
from app.logger import setup_logging, get_logger
from app.routes.analysis import router as analysis_router
from app.routes.health import router as health_router

# ============================================
# 로깅 초기화 — 앱이 켜질 때 1번만 실행
# ============================================
# 비전공자 설명: "앱 시작할 때 일기장 세팅하는 거"
setup_logging()
logger = get_logger("main")

app = FastAPI(
    title="SIGNAL Agent E — AI 분석 엔진",
    description="GPT + Gemini + Grok 3각도 병렬 분석 API",
    version="1.2.0",
)

# CORS 설정 (앱에서 API 호출할 수 있게)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 앱 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# 전역 예외 핸들러
# ============================================
# 비전공자 설명:
# "어디서 에러가 나든, 사용자에게 보여주는 에러 메시지를 깔끔하게 통일"
# 
# 이게 없으면: 에러 나면 서버가 못생긴 HTML 에러페이지를 보여줌
# 이게 있으면: 에러 나도 항상 깔끔한 JSON으로 응답
#
# 형식:
# {
#   "error": true,
#   "status_code": 401,
#   "message": "인증이 필요합니다"
# }
# ============================================


@app.exception_handler(SignalBaseError)
async def signal_error_handler(request: Request, exc: SignalBaseError):
    """
    우리가 정의한 에러 처리 (AuthError, AIServiceError 등)
    → 에러 종류별로 적절한 HTTP 상태 코드 반환
    """
    logger.warning(
        "비즈니스 에러 발생",
        error_type=type(exc).__name__,
        status_code=exc.status_code,
        message=exc.message,
        path=str(request.url),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "message": exc.message,
        },
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """
    예상 못한 에러 처리 (코드 버그 등)
    → 500 Internal Server Error로 통일

    비전공자 설명:
    "뭔지 모르겠는 에러가 나도 서버가 안 죽고, 깔끔한 에러 메시지를 보내줌"
    
    중요: 실제 에러 내용은 사용자에게 안 보여줌 (보안)
    → 서버 로그에서만 확인 가능
    """
    logger.error(
        "예상치 못한 서버 에러",
        error_type=type(exc).__name__,
        error_detail=str(exc),
        path=str(request.url),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "message": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        },
    )


# ============================================
# 서버 시작 이벤트
# ============================================

@app.on_event("startup")
async def startup_event():
    """서버가 시작될 때 로그 남김"""
    logger.info("Agent E 서버 시작", version="1.2.0")


# 라우터 등록
app.include_router(health_router, tags=["Health"])
app.include_router(analysis_router, prefix="/api", tags=["AI Analysis"])
