# ============================================
# AI 분석 라우터 (핵심 API)
# ============================================
# POST /api/ai-analysis 요청을 처리하는 곳
# 비전공자 설명: "사용자가 AI 분석 버튼 누르면 여기로 옴"
#
# [v1.1] 에러 핸들링 강화
# - HTTPException → 커스텀 에러 클래스 (AuthError, SubscriptionError 등)
# - 캐시 에러는 무시하고 계속 진행 (비치명적)
#
# [v1.2] 로깅 추가
# - 요청 수신/완료, 각 단계별 소요시간 기록
# ============================================

import time
from fastapi import APIRouter, Header
from pydantic import BaseModel
from typing import Optional

from app.errors import AuthError, SubscriptionError, NewsNotFoundError, CacheError
from app.logger import get_logger
from app.services.auth import verify_user_token, check_subscription_and_credits
from app.services.cache import get_cached_analysis, save_analysis_to_cache
from app.services.ai_clients import call_all_ai_models
from app.services.supabase_client import get_news_by_id

router = APIRouter()

# 로거 생성
logger = get_logger("analysis")


# --- 요청/응답 모델 (데이터 형태 정의) ---

class AnalysisRequest(BaseModel):
    """
    앱에서 보내는 요청 형태
    - news_id: 분석할 뉴스의 고유 ID
    - models: 어떤 AI를 쓸지 (기본: 3개 전부)
    """
    news_id: str
    models: list[str] = ["gpt", "gemini", "grok"]


# --- 메인 API ---

@router.post("/ai-analysis")
async def analyze_news(
    request: AnalysisRequest,
    authorization: Optional[str] = Header(None),
):
    """
    AI 3각도 분석 API

    흐름:
    1. 사용자 인증 확인 (로그인했나?)
    2. 캐시 확인 (이미 분석한 뉴스인가?)
    3. 구독/크레딧 확인 (분석 가능한 사용자인가?)
    4. 뉴스 내용 가져오기
    5. GPT + Gemini + Grok 3개 동시 호출
    6. Claude로 검증
    7. 결과 저장하고 반환

    [변경점 v1.1]
    - HTTPException 대신 커스텀 에러 사용 → main.py의 전역 핸들러가 처리
    - 캐시 실패해도 서비스는 계속 동작 (비치명적 에러)
    """
    request_start = time.monotonic()
    logger.info("분석 요청 수신", news_id=request.news_id, models=request.models)

    # [1단계] 사용자 인증
    if not authorization:
        logger.warning("인증 토큰 누락", news_id=request.news_id)
        raise AuthError("인증 토큰이 필요합니다")

    token = authorization.replace("Bearer ", "")
    user = await verify_user_token(token)
    if not user:
        raise AuthError("유효하지 않은 토큰입니다")

    # [2단계] 캐시 확인 — 이미 분석된 뉴스면 바로 반환 (비용 0)
    # 캐시 조회 실패해도 서비스는 계속 진행 (그냥 새로 분석하면 됨)
    try:
        cached = await get_cached_analysis(request.news_id)
        if cached:
            total_ms = int((time.monotonic() - request_start) * 1000)
            logger.info("캐시 응답 반환", news_id=request.news_id, total_ms=total_ms)
            return {**cached, "cached": True}
    except Exception as e:
        # 캐시 읽기 실패 → 무시하고 새로 분석 진행
        logger.warning("캐시 조회 실패 — 새로 분석 진행", news_id=request.news_id, error=str(e))

    # [3단계] 구독 상태 & 크레딧 확인
    credit_check = await check_subscription_and_credits(user["id"])
    if not credit_check["allowed"]:
        raise SubscriptionError(
            credit_check.get("reason", "AI 분석 이용권이 부족합니다. 구독을 확인해주세요.")
        )

    # [4단계] 뉴스 내용 가져오기
    news = await get_news_by_id(request.news_id)
    if not news:
        raise NewsNotFoundError(request.news_id)

    # [5~6단계] AI 3개 병렬 호출 + Claude 검증
    # ai_clients.py 내부에서 타임아웃/재시도/격리 처리됨
    analysis_result = await call_all_ai_models(
        news=news,
        requested_models=request.models,
    )

    # [7단계] 결과 캐시 저장
    # 캐시 저장 실패해도 결과는 반환 (비치명적 에러)
    try:
        await save_analysis_to_cache(request.news_id, analysis_result)
    except Exception as e:
        # 캐시 저장 실패 → 무시 (다음에 또 AI 호출하면 됨, 비용만 약간 더 듦)
        logger.warning("캐시 저장 실패", news_id=request.news_id, error=str(e))

    total_ms = int((time.monotonic() - request_start) * 1000)
    success_count = sum(1 for r in analysis_result.values() if not r.get("error"))
    logger.info(
        "분석 요청 완료",
        news_id=request.news_id,
        total_ms=total_ms,
        success_count=success_count,
        cached=False,
    )

    # 면책 고지 포함해서 반환
    return {
        "news_id": request.news_id,
        "news_title": news.get("title", ""),
        "cached": False,
        "analyses": analysis_result,
        "disclaimer": "⚠️ 본 분석은 AI가 생성한 정보이며, 투자 권유가 아닙니다. 투자 판단 및 결과에 대한 책임은 이용자 본인에게 있습니다.",
    }
