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
    """이미 수집된 뉴스인지 source_url로 중복 체크
    - True면 이미 있음 (중복)
    - False면 새 뉴스
    """
    response = supabase.table("news") \
        .select("id") \
        .eq("source_url", source_url) \
        .execute()
    return len(response.data) > 0


async def save_news(supabase: Client, news_data: dict) -> dict:
    """뉴스를 news 테이블에 저장하는 함수
    - news_data는 DB 스키마(01_db_schema.md)의 컬럼명과 일치해야 함
    """
    response = supabase.table("news") \
        .insert(news_data) \
        .execute()
    return response.data[0] if response.data else {}


async def save_news_batch(supabase: Client, news_list: list[dict]) -> list:
    """여러 뉴스를 한 번에 저장하는 함수 (배치 처리)"""
    if not news_list:
        return []
    response = supabase.table("news") \
        .insert(news_list) \
        .execute()
    return response.data


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
