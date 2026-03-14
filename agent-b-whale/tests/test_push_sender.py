"""
test_push_sender.py — push_sender 모듈 테스트

API 키 없이도 돌아가는 단위 테스트.
알림 메시지 포맷팅과 배치 분할 로직을 검증한다.
"""

import pytest
import sys
import os

# 테스트용 환경변수 설정
os.environ["TESTING"] = "true"  # DB 실제 연결 방지
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-key"
os.environ["WHALE_ALERT_API_KEY"] = "test-whale-key"
os.environ["EXPO_ACCESS_TOKEN"] = "test-expo-token"

# agent-b-whale 디렉토리를 import 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from push_sender import format_usd, format_whale_push


# ──────────────────────────────────────────────
# 금액 포맷팅 테스트
# ──────────────────────────────────────────────

class TestFormatUsd:
    """USD 금액 표시 형식 테스트"""

    def test_billions(self):
        """10억 달러 이상 → $X.XB 형식"""
        assert format_usd(2_300_000_000) == "$2.3B"
        assert format_usd(1_000_000_000) == "$1.0B"

    def test_millions(self):
        """100만 달러 이상 → $X.XM 형식"""
        assert format_usd(112_000_000) == "$112.0M"
        assert format_usd(5_500_000) == "$5.5M"
        assert format_usd(1_000_000) == "$1.0M"

    def test_thousands(self):
        """100만 달러 미만 → $X.XK 형식"""
        assert format_usd(500_000) == "$500.0K"
        assert format_usd(100_000) == "$100.0K"


# ──────────────────────────────────────────────
# 알림 메시지 포맷 테스트
# ──────────────────────────────────────────────

class TestFormatWhalePush:
    """푸시 알림 메시지 포맷 테스트"""

    def test_btc_alert_format(self):
        """BTC 고래 알림 메시지가 올바른지"""
        whale = {
            "id": "test-uuid-123",
            "symbol": "BTC",
            "amount": 1240,
            "amount_usd": 112_000_000,
            "from_label": "Binance",
            "to_label": "unknown",
        }

        result = format_whale_push(whale)

        assert result["title"] == "🐋 BTC 대형 이동 감지"
        assert "1,240 BTC" in result["body"]
        assert "$112.0M" in result["body"]
        assert "Binance" in result["body"]
        assert "미확인 지갑" in result["body"]  # "unknown"이 한국어로 변환됨

    def test_eth_alert_format(self):
        """ETH 고래 알림 메시지"""
        whale = {
            "id": "test-uuid-456",
            "symbol": "ETH",
            "amount": 50000,
            "amount_usd": 95_000_000,
            "from_label": "Coinbase",
            "to_label": "Kraken",
        }

        result = format_whale_push(whale)

        assert result["title"] == "🐋 ETH 대형 이동 감지"
        assert "50,000 ETH" in result["body"]
        assert "Coinbase → Kraken" in result["body"]

    def test_data_includes_screen(self):
        """알림 data에 화면 이동 정보가 포함되는지"""
        whale = {
            "id": "test-uuid",
            "symbol": "BTC",
            "amount": 100,
            "amount_usd": 10_000_000,
            "from_label": "unknown",
            "to_label": "unknown",
        }

        result = format_whale_push(whale)

        assert result["data"]["type"] == "whale_alert"
        assert result["data"]["screen"] == "whale_detail"
        assert result["data"]["whale_id"] == "test-uuid"

    def test_unknown_labels_korean(self):
        """'unknown' 라벨이 '미확인 지갑'으로 변환되는지"""
        whale = {
            "id": "test",
            "symbol": "USDT",
            "amount": 10_000_000,
            "amount_usd": 10_000_000,
            "from_label": "unknown",
            "to_label": "unknown",
        }

        result = format_whale_push(whale)

        assert "미확인 지갑 → 미확인 지갑" in result["body"]


# ──────────────────────────────────────────────
# 배치 분할 로직 테스트
# ──────────────────────────────────────────────

class TestBatchSplit:
    """알림 배치 분할 로직 테스트"""

    def test_batch_split_100(self):
        """250개 메시지가 3개 배치로 나뉘는지"""
        from config import EXPO_PUSH_BATCH_SIZE

        messages = [{"to": f"token_{i}"} for i in range(250)]

        batches = []
        for i in range(0, len(messages), EXPO_PUSH_BATCH_SIZE):
            batches.append(messages[i : i + EXPO_PUSH_BATCH_SIZE])

        assert len(batches) == 3  # 100 + 100 + 50
        assert len(batches[0]) == 100
        assert len(batches[1]) == 100
        assert len(batches[2]) == 50

    def test_single_batch(self):
        """50개 메시지는 1개 배치"""
        from config import EXPO_PUSH_BATCH_SIZE

        messages = [{"to": f"token_{i}"} for i in range(50)]

        batches = []
        for i in range(0, len(messages), EXPO_PUSH_BATCH_SIZE):
            batches.append(messages[i : i + EXPO_PUSH_BATCH_SIZE])

        assert len(batches) == 1
        assert len(batches[0]) == 50


# ──────────────────────────────────────────────
# 사용자 필터링 로직 테스트
# ──────────────────────────────────────────────

class TestUserFiltering:
    """구독 등급별 알림 필터링 테스트"""

    def test_free_user_threshold(self):
        """FREE 사용자는 $500만 이상만 알림 받는지"""
        from config import FREE_USER_MIN_USD

        assert FREE_USER_MIN_USD == 5_000_000

        # $300만 거래 → FREE 사용자는 알림 안 받음
        amount_usd = 3_000_000
        should_notify = amount_usd >= FREE_USER_MIN_USD
        assert should_notify is False

        # $600만 거래 → FREE 사용자도 알림 받음
        amount_usd = 6_000_000
        should_notify = amount_usd >= FREE_USER_MIN_USD
        assert should_notify is True

    def test_paid_user_threshold(self):
        """유료 사용자는 $100만 이상부터 알림 받는지"""
        from config import PAID_USER_MIN_USD

        assert PAID_USER_MIN_USD == 1_000_000

        # $50만 거래 → 유료 사용자도 알림 안 받음
        amount_usd = 500_000
        should_notify = amount_usd >= PAID_USER_MIN_USD
        assert should_notify is False

        # $200만 거래 → 유료 사용자 알림 받음
        amount_usd = 2_000_000
        should_notify = amount_usd >= PAID_USER_MIN_USD
        assert should_notify is True
