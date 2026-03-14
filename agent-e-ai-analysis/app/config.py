# ============================================
# 앱 설정 (환경변수 로드)
# ============================================
# .env 파일에서 값을 읽어오는 설정 클래스
# 비전공자 설명: "앱이 켜질 때 필요한 모든 비밀 키를 한곳에서 관리"
# ============================================

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    .env 파일에 있는 값들을 여기서 자동으로 읽어옴.
    예: SUPABASE_URL=https://xxx.supabase.co → settings.supabase_url 로 사용
    """

    # --- Supabase ---
    supabase_url: str = ""
    supabase_service_key: str = ""

    # --- AI API Keys ---
    openai_api_key: str = ""
    google_api_key: str = ""
    xai_api_key: str = ""
    anthropic_api_key: str = ""

    # --- 설정값 ---
    cache_ttl_hours: int = 24            # 캐시 유효시간 (시간)
    max_tokens_per_model: int = 500      # AI 응답 최대 길이
    rate_limit_per_user_per_day: int = 100  # 하루 최대 분석 횟수

    class Config:
        env_file = ".env"  # .env 파일에서 자동 로드


# 앱 전체에서 공유하는 설정 인스턴스
settings = Settings()
