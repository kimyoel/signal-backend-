"""
config.py — 설정값 관리 모듈

쉽게 말하면: 앱에서 쓰는 모든 비밀키(API 키 등)와 설정값을 한 곳에서 관리하는 파일.
다른 파일에서 from config import XXX 로 불러서 쓴다.

⚠️ 절대 이 파일에 실제 키 값을 적지 마세요!
   모든 비밀키는 .env 파일 또는 Railway 환경변수에 설정합니다.
"""

import os
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드 (로컬 개발용)
# Railway에서는 환경변수가 자동으로 설정되므로 .env 파일 불필요
load_dotenv()


# ──────────────────────────────────────────────
# Supabase (데이터베이스)
# ──────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# ──────────────────────────────────────────────
# Whale Alert API (고래 거래 감지)
# ──────────────────────────────────────────────
WHALE_ALERT_API_KEY = os.getenv("WHALE_ALERT_API_KEY", "")
WHALE_ALERT_BASE_URL = "https://api.whale-alert.io/v1/transactions"

# 최소 감지 금액 (USD) — 이 금액 이상의 거래만 가져옴
WHALE_MIN_VALUE_USD = 1_000_000  # $100만

# 감시 대상 코인 목록
WHALE_TRACKED_SYMBOLS = ["BTC", "ETH", "USDT", "USDC", "SOL"]

# 폴링 간격 (초) — 5분 = 300초
POLLING_INTERVAL_SECONDS = 300

# ──────────────────────────────────────────────
# Expo Push Notifications (앱 알림)
# ──────────────────────────────────────────────
EXPO_ACCESS_TOKEN = os.getenv("EXPO_ACCESS_TOKEN", "")
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

# 한 번에 보내는 최대 알림 수 (Expo 제한)
EXPO_PUSH_BATCH_SIZE = 100

# ──────────────────────────────────────────────
# 사용자별 알림 기준
# ──────────────────────────────────────────────
# FREE 사용자: $500만 이상만 알림 (과도한 알림 방지)
FREE_USER_MIN_USD = 5_000_000

# BASIC/PRO 사용자: $100만 이상 알림
PAID_USER_MIN_USD = 1_000_000


def validate_config():
    """
    필수 환경변수가 설정되어 있는지 확인하는 함수.
    빠진 게 있으면 어떤 키가 없는지 알려준다.
    """
    required = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_SERVICE_ROLE_KEY,
        "WHALE_ALERT_API_KEY": WHALE_ALERT_API_KEY,
        "EXPO_ACCESS_TOKEN": EXPO_ACCESS_TOKEN,
    }

    missing = [key for key, value in required.items() if not value]

    if missing:
        print("=" * 50)
        print("⚠️  아래 환경변수가 설정되지 않았습니다!")
        print("=" * 50)
        for key in missing:
            print(f"  ❌ {key}")
        print()
        print("💡 해결 방법:")
        print("  1. .env 파일을 만들고 값을 채워넣으세요 (.env.example 참고)")
        print("  2. Railway 배포 시에는 환경변수 탭에서 설정하세요")
        print("=" * 50)
        return False

    print("✅ 모든 환경변수가 정상적으로 설정되었습니다.")
    return True
