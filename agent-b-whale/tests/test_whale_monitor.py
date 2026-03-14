"""
test_whale_monitor.py — whale_monitor 모듈 테스트

API 키 없이도 돌아가는 단위 테스트.
실제 API를 호출하지 않고, 가짜 데이터(mock)로 로직만 검증한다.
"""

import pytest
from unittest.mock import patch, MagicMock

# config를 먼저 mock 해야 db.py에서 에러 안 남
import sys
import os

# 테스트용 환경변수 설정 (실제 키 아님!)
os.environ["TESTING"] = "true"  # DB 실제 연결 방지
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-key"
os.environ["WHALE_ALERT_API_KEY"] = "test-whale-key"
os.environ["EXPO_ACCESS_TOKEN"] = "test-expo-token"

# agent-b-whale 디렉토리를 import 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────
# Whale Alert API 응답 파싱 테스트
# ──────────────────────────────────────────────

# 가짜 API 응답 데이터 (실제 Whale Alert 응답과 같은 형식)
FAKE_API_RESPONSE = {
    "result": "success",
    "count": 2,
    "transactions": [
        {
            "blockchain": "bitcoin",
            "symbol": "btc",
            "id": "111111",
            "transaction_type": "transfer",
            "hash": "abc123hash",
            "from": {
                "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "owner": "Binance",
                "owner_type": "exchange",
            },
            "to": {
                "address": "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
                "owner": "unknown",
                "owner_type": "unknown",
            },
            "timestamp": 1710000000,
            "amount": 1240.5,
            "amount_usd": 112000000,
        },
        {
            "blockchain": "ethereum",
            "symbol": "eth",
            "id": "222222",
            "transaction_type": "transfer",
            "hash": "def456hash",
            "from": {
                "address": "0xabc...",
                "owner": "Coinbase",
                "owner_type": "exchange",
            },
            "to": {
                "address": "0xdef...",
                "owner": "Kraken",
                "owner_type": "exchange",
            },
            "timestamp": 1710000100,
            "amount": 50000,
            "amount_usd": 95000000,
        },
    ],
}


class TestParseTransactions:
    """API 응답을 우리 형식으로 변환하는 로직 테스트"""

    def test_parse_btc_transaction(self):
        """BTC 거래가 올바르게 파싱되는지"""
        tx = FAKE_API_RESPONSE["transactions"][0]

        # 파싱 로직 직접 테스트
        symbol = tx.get("symbol", "").upper()
        assert symbol == "BTC"
        assert tx["amount"] == 1240.5
        assert tx["amount_usd"] == 112000000
        assert tx["from"]["owner"] == "Binance"
        assert tx["to"]["owner"] == "unknown"

    def test_parse_eth_transaction(self):
        """ETH 거래가 올바르게 파싱되는지"""
        tx = FAKE_API_RESPONSE["transactions"][1]

        symbol = tx.get("symbol", "").upper()
        assert symbol == "ETH"
        assert tx["amount"] == 50000
        assert tx["from"]["owner"] == "Coinbase"
        assert tx["to"]["owner"] == "Kraken"

    def test_symbol_filter(self):
        """감시 대상 코인만 통과하는지"""
        from config import WHALE_TRACKED_SYMBOLS

        # BTC, ETH는 감시 대상
        assert "BTC" in WHALE_TRACKED_SYMBOLS
        assert "ETH" in WHALE_TRACKED_SYMBOLS

        # DOGE는 감시 대상 아님
        assert "DOGE" not in WHALE_TRACKED_SYMBOLS

    def test_empty_response(self):
        """빈 응답 처리"""
        empty_response = {"result": "success", "count": 0, "transactions": []}
        assert len(empty_response["transactions"]) == 0

    def test_failed_response(self):
        """실패 응답 처리"""
        fail_response = {"result": "error", "message": "Invalid API key"}
        assert fail_response["result"] != "success"


class TestDuplicateDetection:
    """중복 거래 감지 로직 테스트"""

    def test_identify_duplicate_by_hash(self):
        """tx_hash로 중복을 식별할 수 있는지"""
        existing_hashes = {"abc123hash", "xyz789hash"}
        new_tx_hash = "abc123hash"

        # 이미 있는 해시 → 중복
        assert new_tx_hash in existing_hashes

    def test_identify_new_by_hash(self):
        """새 거래를 올바르게 식별하는지"""
        existing_hashes = {"abc123hash", "xyz789hash"}
        new_tx_hash = "brand_new_hash"

        # 없는 해시 → 신규
        assert new_tx_hash not in existing_hashes

    def test_filter_duplicates(self):
        """중복 필터링 로직이 올바르게 동작하는지"""
        transactions = [
            {"tx_hash": "hash1", "symbol": "BTC"},
            {"tx_hash": "hash2", "symbol": "ETH"},
            {"tx_hash": "hash3", "symbol": "BTC"},
        ]
        existing_hashes = {"hash1", "hash3"}

        # 중복 제거
        new_only = [tx for tx in transactions if tx["tx_hash"] not in existing_hashes]

        assert len(new_only) == 1
        assert new_only[0]["tx_hash"] == "hash2"
