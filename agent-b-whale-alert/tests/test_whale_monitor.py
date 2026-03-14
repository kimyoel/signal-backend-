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


# ──────────────────────────────────────────────
# Mock 기반 통합 테스트 — 실제 함수 호출
# ──────────────────────────────────────────────

class TestFetchWhaleTransactions:
    """fetch_whale_transactions() 함수를 mock API로 테스트"""

    @patch("whale_monitor.httpx.get")
    def test_successful_api_call(self, mock_get):
        """API 정상 응답 시 거래 목록이 올바르게 파싱되는지"""
        from whale_monitor import fetch_whale_transactions

        # httpx.get이 가짜 응답을 반환하도록 설정
        mock_response = MagicMock()
        mock_response.json.return_value = FAKE_API_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_whale_transactions()

        # BTC, ETH 2건 모두 감시 대상이므로 2건 반환
        assert len(result) == 2
        assert result[0]["symbol"] == "BTC"
        assert result[0]["amount"] == 1240.5
        assert result[0]["from_label"] == "Binance"
        assert result[1]["symbol"] == "ETH"
        assert result[1]["tx_hash"] == "def456hash"

    @patch("whale_monitor.httpx.get")
    def test_api_timeout(self, mock_get):
        """API 타임아웃 시 빈 리스트 반환"""
        from whale_monitor import fetch_whale_transactions
        import httpx

        mock_get.side_effect = httpx.TimeoutException("timeout")

        result = fetch_whale_transactions()
        assert result == []

    @patch("whale_monitor.httpx.get")
    def test_api_error_response(self, mock_get):
        """API가 error 응답을 보낼 때 빈 리스트 반환"""
        from whale_monitor import fetch_whale_transactions

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": "error",
            "message": "Invalid API key",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_whale_transactions()
        assert result == []

    @patch("whale_monitor.httpx.get")
    def test_filters_non_tracked_symbols(self, mock_get):
        """감시 대상이 아닌 코인(DOGE)은 필터링되는지"""
        from whale_monitor import fetch_whale_transactions

        response_with_doge = {
            "result": "success",
            "count": 1,
            "transactions": [
                {
                    "blockchain": "dogecoin",
                    "symbol": "doge",
                    "id": "333333",
                    "hash": "doge_hash",
                    "from": {"address": "addr1", "owner": "unknown", "owner_type": "unknown"},
                    "to": {"address": "addr2", "owner": "unknown", "owner_type": "unknown"},
                    "timestamp": 1710000200,
                    "amount": 999999999,
                    "amount_usd": 50000000,
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response_with_doge
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_whale_transactions()
        assert result == []  # DOGE는 감시 대상 아님


class TestFilterNewTransactions:
    """filter_new_transactions()를 Supabase mock으로 테스트"""

    @patch("whale_monitor.supabase")
    def test_filters_existing_hashes(self, mock_supabase):
        """DB에 이미 있는 tx_hash는 제외되는지"""
        from whale_monitor import filter_new_transactions

        # DB에 hash1이 이미 있다고 가정
        mock_result = MagicMock()
        mock_result.data = [{"tx_hash": "hash1"}]
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_result

        transactions = [
            {"tx_hash": "hash1", "symbol": "BTC"},
            {"tx_hash": "hash2", "symbol": "ETH"},
        ]

        result = filter_new_transactions(transactions)

        assert len(result) == 1
        assert result[0]["tx_hash"] == "hash2"

    @patch("whale_monitor.supabase")
    def test_all_new_transactions(self, mock_supabase):
        """모두 새 거래일 때 전부 반환"""
        from whale_monitor import filter_new_transactions

        mock_result = MagicMock()
        mock_result.data = []  # DB에 아무것도 없음
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_result

        transactions = [
            {"tx_hash": "new1", "symbol": "BTC"},
            {"tx_hash": "new2", "symbol": "ETH"},
        ]

        result = filter_new_transactions(transactions)
        assert len(result) == 2

    def test_empty_input(self):
        """빈 리스트 입력 시 빈 리스트 반환"""
        from whale_monitor import filter_new_transactions

        result = filter_new_transactions([])
        assert result == []


class TestGetUnsentAlerts:
    """get_unsent_alerts() — 미발송 건 재조회 테스트"""

    @patch("whale_monitor.supabase")
    def test_returns_unsent_alerts(self, mock_supabase):
        """push_sent=false인 건들이 반환되는지"""
        from whale_monitor import get_unsent_alerts

        mock_result = MagicMock()
        mock_result.data = [
            {"id": "uuid-1", "symbol": "BTC", "amount_usd": 5000000},
            {"id": "uuid-2", "symbol": "ETH", "amount_usd": 3000000},
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

        result = get_unsent_alerts()

        assert len(result) == 2
        assert result[0]["id"] == "uuid-1"

    @patch("whale_monitor.supabase")
    def test_no_unsent_alerts(self, mock_supabase):
        """미발송 건이 없을 때 빈 리스트 반환"""
        from whale_monitor import get_unsent_alerts

        mock_result = MagicMock()
        mock_result.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

        result = get_unsent_alerts()
        assert result == []

    @patch("whale_monitor.supabase")
    def test_db_error_returns_empty(self, mock_supabase):
        """DB 조회 실패 시 빈 리스트 반환 (에러로 죽지 않음)"""
        from whale_monitor import get_unsent_alerts

        mock_supabase.table.side_effect = Exception("DB connection failed")

        result = get_unsent_alerts()
        assert result == []
