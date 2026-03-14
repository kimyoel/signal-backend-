# ─────────────────────────────────────────
# sources.py — RSS/뉴스 소스 목록 관리
# Supabase analyst_sources 테이블에서 소스를 로드
# ─────────────────────────────────────────

from db import get_supabase_client, get_active_sources

# ──────────────────────────────────────────
# NewsAPI 검색 키워드 목록
# 이 키워드들로 NewsAPI에서 뉴스를 검색함
# ──────────────────────────────────────────
NEWSAPI_KEYWORDS = [
    "federal reserve",     # 연준
    "interest rate",       # 금리
    "bitcoin",             # 비트코인
    "ethereum",            # 이더리움
    "cryptocurrency",      # 암호화폐
    "nasdaq",              # 나스닥
    "S&P 500",             # S&P 500
    "inflation",           # 인플레이션
    "금리",                # 한국어 키워드
    "비트코인",            # 한국어 키워드
]


async def load_rss_sources() -> list[dict]:
    """Supabase에서 활성화된 RSS 소스 목록을 가져오는 함수

    반환 형식:
    [
        {
            "name": "Reuters Business",
            "source_url": "https://feeds.reuters.com/reuters/businessNews",
            "category": "macro",
            "source_type": "rss",
            "priority": 5
        },
        ...
    ]
    """
    supabase = get_supabase_client()
    sources = await get_active_sources(supabase)
    return sources
