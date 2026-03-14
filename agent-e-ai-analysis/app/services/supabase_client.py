# ============================================
# Supabase 클라이언트 (DB 연결)
# ============================================
# Supabase = 우리 앱의 데이터베이스 + 인증 서비스
# 비전공자 설명: "모든 데이터를 저장하고 꺼내오는 창고 연결"
# ============================================

from supabase import create_client, Client
from app.config import settings

# Supabase 클라이언트 생성 (앱 시작 시 1번만)
_supabase: Client | None = None


def get_supabase() -> Client:
    """Supabase 연결을 가져오는 함수 (한 번만 연결하고 재사용)"""
    global _supabase
    if _supabase is None:
        _supabase = create_client(
            settings.supabase_url,
            settings.supabase_service_key,
        )
    return _supabase


async def get_news_by_id(news_id: str) -> dict | None:
    """
    뉴스 ID로 뉴스 1개를 가져오는 함수

    예시: get_news_by_id("abc-123")
    → { "id": "abc-123", "title": "Fed 금리 동결...", "summary": "...", ... }
    """
    supabase = get_supabase()
    result = supabase.table("news").select("*").eq("id", news_id).execute()

    if result.data and len(result.data) > 0:
        return result.data[0]
    return None
