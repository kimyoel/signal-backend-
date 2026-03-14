# ─────────────────────────────────────────
# db.py — Supabase 연결 + 쿼리 함수
# 모든 DB 관련 작업은 이 파일을 통해서만 수행
# ─────────────────────────────────────────

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드 (Railway에서는 환경변수가 자동 주입됨)
load_dotenv()

# ──────────────────────────────────────────
# Supabase 클라이언트 초기화
# ──────────────────────────────────────────
def get_supabase_client() -> Client:
    """Supabase 클라이언트를 생성해서 반환하는 함수"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY 환경변수가 설정되지 않았습니다.")

    return create_client(url, key)


# ──────────────────────────────────────────
# 뉴스 관련 쿼리
# ──────────────────────────────────────────

async def get_active_sources(supabase: Client) -> list:
    """활성화된 RSS/뉴스 소스 목록을 가져오는 함수
    - analyst_sources 테이블에서 is_active=true 인 것만
    """
    response = supabase.table("analyst_sources") \
        .select("*") \
        .eq("is_active", True) \
        .execute()
    return response.data


async def check_duplicate_url(supabase: Client, source_url: str) -> bool:
    """이미 수집된 뉴스인지 source_url로 중복 체크 (단건 — 하위호환용)
    - True면 이미 있음 (중복)
    - False면 새 뉴스
    """
    response = supabase.table("news") \
        .select("id") \
        .eq("source_url", source_url) \
        .execute()
    return len(response.data) > 0


async def check_duplicate_urls_batch(supabase: Client, source_urls: list[str]) -> set[str]:
    """여러 URL을 한 번의 IN 쿼리로 중복 체크 (배치 버전)
    - N번 개별 쿼리 → 1번 IN 쿼리로 최대 500배 빠름
    - 반환: 이미 DB에 있는 URL 집합 (set)
    """
    if not source_urls:
        return set()

    # Supabase에서 IN 쿼리: .in_("source_url", [...])
    response = supabase.table("news") \
        .select("source_url") \
        .in_("source_url", source_urls) \
        .execute()

    existing = {row["source_url"] for row in (response.data or [])}
    return existing


async def save_news(supabase: Client, news_data: dict) -> dict:
    """뉴스를 news 테이블에 저장하는 함수
    - content_type 컬럼이 없으면 자동으로 제거 (하위호환)
    """
    # content_type 컬럼이 스키마에 없는 경우 대비
    safe_data = {k: v for k, v in news_data.items() if k != "content_type"}
    try:
        response = supabase.table("news") \
            .insert(news_data) \
            .execute()
        return response.data[0] if response.data else {}
    except Exception:
        # content_type 컬럼 없을 경우 fallback
        response = supabase.table("news") \
            .insert(safe_data) \
            .execute()
        return response.data[0] if response.data else {}


async def save_news_batch(supabase: Client, news_list: list[dict]) -> list:
    """여러 뉴스를 한 번에 저장하는 함수 (배치 처리)
    - content_type 컬럼 없을 경우 자동 fallback
    """
    if not news_list:
        return []
    try:
        response = supabase.table("news") \
            .insert(news_list) \
            .execute()
        return response.data
    except Exception as e:
        err_str = str(e)
        # content_type 컬럼 미존재 오류면 해당 필드 제거 후 재시도
        if "content_type" in err_str or "PGRST204" in err_str:
            safe_list = [{k: v for k, v in item.items() if k != "content_type"} for item in news_list]
            response = supabase.table("news") \
                .insert(safe_list) \
                .execute()
            return response.data
        raise


# ──────────────────────────────────────────
# AI 분석 관련 쿼리
# ──────────────────────────────────────────

async def get_news_by_id(supabase: Client, news_id: str) -> dict | None:
    """news_id로 뉴스 1건 조회"""
    response = supabase.table("news") \
        .select("*") \
        .eq("id", news_id) \
        .single() \
        .execute()
    return response.data


async def get_cached_analysis(supabase: Client, news_id: str) -> dict | None:
    """이미 생성된 AI 분석 결과가 있는지 캐시 확인
    - 있으면 dict 반환 (GPT 비용 절약!)
    - 없으면 None 반환
    """
    response = supabase.table("ai_analyses") \
        .select("*") \
        .eq("news_id", news_id) \
        .execute()
    return response.data[0] if response.data else None


async def save_analysis(supabase: Client, analysis_data: dict) -> dict:
    """AI 분석 결과를 ai_analyses 테이블에 저장"""
    response = supabase.table("ai_analyses") \
        .insert(analysis_data) \
        .execute()
    return response.data[0] if response.data else {}


async def update_news_has_analysis(supabase: Client, news_id: str) -> None:
    """뉴스에 AI 분석이 생성되었음을 표시 (has_analysis = true)"""
    supabase.table("news") \
        .update({"has_analysis": True}) \
        .eq("id", news_id) \
        .execute()


# ──────────────────────────────────────────
# 사용자/크레딧 관련 쿼리
# ──────────────────────────────────────────

async def get_user_credits(supabase: Client, user_id: str) -> int:
    """사용자의 AI 분석 크레딧 잔여량 조회
    - -1이면 무제한 (BASIC/PRO 구독자)
    - 0이면 소진됨
    - 양수면 남은 횟수
    """
    response = supabase.table("users") \
        .select("ai_credits") \
        .eq("id", user_id) \
        .single() \
        .execute()
    return response.data["ai_credits"] if response.data else 0


async def deduct_credit(supabase: Client, user_id: str) -> bool:
    """크레딧 1회 차감 (FREE 사용자만)
    - ai_credits > 0 인 경우만 차감
    - 차감 성공하면 True, 실패하면 False
    """
    # 먼저 현재 크레딧 확인
    credits = await get_user_credits(supabase, user_id)

    if credits == -1:
        # 무제한 사용자 → 차감 불필요
        return True
    elif credits > 0:
        # 1 차감
        supabase.table("users") \
            .update({"ai_credits": credits - 1}) \
            .eq("id", user_id) \
            .execute()
        return True
    else:
        # 크레딧 부족
        return False
