# ============================================
# 인증 & 구독 확인 서비스
# ============================================
# 사용자가 로그인했는지, 유료인지 확인하는 로직
# 비전공자 설명: "입장권 검사하는 직원"
# ============================================

from app.services.supabase_client import get_supabase


async def verify_user_token(token: str) -> dict | None:
    """
    Supabase JWT 토큰을 검증해서 사용자 정보를 반환

    비전공자 설명:
    - 사용자가 앱에서 로그인하면 "신분증(토큰)"을 받음
    - 이 함수는 그 신분증이 진짜인지 확인하는 역할
    - 진짜면 → 사용자 정보 반환
    - 가짜면 → None 반환 (입장 거부)
    """
    try:
        supabase = get_supabase()
        user_response = supabase.auth.get_user(token)
        if user_response and user_response.user:
            return {
                "id": user_response.user.id,
                "email": user_response.user.email,
            }
        return None
    except Exception:
        return None


async def check_subscription_and_credits(user_id: str) -> dict:
    """
    사용자의 구독 상태와 AI 크레딧을 확인

    비전공자 설명:
    - "이 사람이 AI 분석을 쓸 수 있는 사람인지" 확인
    - 무료 사용자: 월 5회 제한 (남은 횟수 확인)
    - 유료 사용자: 무제한 (ai_credits = -1)

    반환값:
    - allowed: True → 분석 가능 / False → 분석 불가
    - reason: 불가 시 이유 설명
    """
    supabase = get_supabase()

    # 사용자 정보에서 크레딧 확인
    result = supabase.table("users").select("ai_credits").eq("id", user_id).execute()

    if not result.data or len(result.data) == 0:
        return {"allowed": False, "reason": "사용자 정보를 찾을 수 없습니다"}

    user = result.data[0]
    ai_credits = user.get("ai_credits", 0)

    # ai_credits = -1 → 무제한 (유료 구독자)
    if ai_credits == -1:
        return {"allowed": True}

    # ai_credits > 0 → 차감 후 허용
    if ai_credits > 0:
        # 크레딧 1 차감
        supabase.table("users").update(
            {"ai_credits": ai_credits - 1}
        ).eq("id", user_id).execute()
        return {"allowed": True, "remaining_credits": ai_credits - 1}

    # ai_credits = 0 → 무료 크레딧 소진
    return {
        "allowed": False,
        "reason": "이번 달 무료 AI 분석 횟수를 모두 사용했습니다. 구독하시면 무제한으로 이용 가능합니다!",
    }
