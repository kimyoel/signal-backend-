# ============================================
# AI 분석 라우터 (핵심 API)
# ============================================
# POST /api/ai-analysis 요청을 처리하는 곳
# 비전공자 설명: "사용자가 AI 분석 버튼 누르면 여기로 옴"
# ============================================

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.services.auth import verify_user_token, check_subscription_and_credits
from app.services.cache import get_cached_analysis, save_analysis_to_cache
from app.services.ai_clients import call_all_ai_models
from app.services.supabase_client import get_news_by_id

router = APIRouter()


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
    """

    # [1단계] 사용자 인증
    if not authorization:
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다")

    token = authorization.replace("Bearer ", "")
    user = await verify_user_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    # [2단계] 캐시 확인 — 이미 분석된 뉴스면 바로 반환 (비용 0)
    cached = await get_cached_analysis(request.news_id)
    if cached:
        return {**cached, "cached": True}

    # [3단계] 구독 상태 & 크레딧 확인
    credit_check = await check_subscription_and_credits(user["id"])
    if not credit_check["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=credit_check.get("reason", "AI 분석 이용권이 부족합니다. 구독을 확인해주세요.")
        )

    # [4단계] 뉴스 내용 가져오기
    news = await get_news_by_id(request.news_id)
    if not news:
        raise HTTPException(status_code=404, detail="해당 뉴스를 찾을 수 없습니다")

    # [5~6단계] AI 3개 병렬 호출 + Claude 검증
    analysis_result = await call_all_ai_models(
        news=news,
        requested_models=request.models,
    )

    # [7단계] 결과 캐시 저장
    await save_analysis_to_cache(request.news_id, analysis_result)

    # 면책 고지 포함해서 반환
    return {
        "news_id": request.news_id,
        "news_title": news.get("title", ""),
        "cached": False,
        "analyses": analysis_result,
        "disclaimer": "⚠️ 본 분석은 AI가 생성한 정보이며, 투자 권유가 아닙니다. 투자 판단 및 결과에 대한 책임은 이용자 본인에게 있습니다.",
    }
