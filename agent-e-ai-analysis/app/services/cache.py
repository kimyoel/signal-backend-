# ============================================
# 캐시 서비스 (비용 절감 핵심!)
# ============================================
# 같은 뉴스를 여러 사용자가 분석 요청하면
# 첫 번째만 AI 호출하고, 나머지는 저장된 결과를 재활용
#
# 비전공자 설명:
# "한 번 계산한 답은 저장해두고, 또 물어보면 저장된 거 바로 보여주기"
# "이렇게 하면 AI 비용을 70%까지 아낄 수 있음!"
# ============================================

import json
from datetime import datetime, timezone, timedelta

from app.config import settings
from app.services.supabase_client import get_supabase


async def get_cached_analysis(news_id: str) -> dict | None:
    """
    캐시된 분석 결과가 있는지 확인

    - 24시간 이내의 분석 결과가 있으면 → 바로 반환 (비용 0원!)
    - 없거나 24시간 지났으면 → None 반환 (새로 분석 필요)
    """
    supabase = get_supabase()

    # 캐시 유효시간 계산 (현재 시간 - 24시간)
    ttl = timedelta(hours=settings.cache_ttl_hours)
    cutoff = (datetime.now(timezone.utc) - ttl).isoformat()

    result = (
        supabase.table("ai_analyses")
        .select("*")
        .eq("news_id", news_id)
        .gte("generated_at", cutoff)  # 캐시 유효시간 내인 것만
        .execute()
    )

    if result.data and len(result.data) > 0:
        row = result.data[0]
        # DB에 저장된 형태를 API 응답 형태로 변환
        return {
            "news_id": news_id,
            "analyses": {
                "gpt": {
                    "model": row.get("gpt_model", "GPT-4o"),
                    "angle": "매크로 경제",
                    "icon": "📊",
                    "content": row.get("gpt_analysis", ""),
                    "generated_at": row.get("generated_at", ""),
                },
                "gemini": {
                    "model": row.get("gemini_model", "Gemini 1.5 Flash"),
                    "angle": "데이터 & 온체인",
                    "icon": "🔗",
                    "content": row.get("gemini_analysis", ""),
                    "generated_at": row.get("generated_at", ""),
                },
                "grok": {
                    "model": row.get("grok_model", "Grok-2"),
                    "angle": "소셜 심리",
                    "icon": "📱",
                    "content": row.get("grok_analysis", ""),
                    "generated_at": row.get("generated_at", ""),
                },
            },
            "verified": row.get("verified", False),
        }

    return None


async def save_analysis_to_cache(news_id: str, analyses: dict) -> None:
    """
    분석 결과를 DB에 저장 (다음 번에 캐시로 재활용)

    비전공자 설명:
    "계산한 답을 노트에 적어두는 것"
    "다음에 같은 질문 오면 노트를 보여주면 끝!"
    """
    supabase = get_supabase()

    # 기존 캐시가 있으면 업데이트, 없으면 새로 생성 (upsert)
    data = {
        "news_id": news_id,
        "gpt_analysis": analyses.get("gpt", {}).get("content", ""),
        "gpt_model": analyses.get("gpt", {}).get("model", "GPT-4o"),
        "gemini_analysis": analyses.get("gemini", {}).get("content", ""),
        "gemini_model": analyses.get("gemini", {}).get("model", "Gemini 1.5 Flash"),
        "grok_analysis": analyses.get("grok", {}).get("content", ""),
        "grok_model": analyses.get("grok", {}).get("model", "Grok-2"),
        "verified": all(
            a.get("verified", False)
            for a in analyses.values()
            if isinstance(a, dict)
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    supabase.table("ai_analyses").upsert(
        data, on_conflict="news_id"
    ).execute()

    # news 테이블에 "이 뉴스는 분석 완료됨" 표시
    supabase.table("news").update(
        {"has_analysis": True}
    ).eq("id", news_id).execute()
