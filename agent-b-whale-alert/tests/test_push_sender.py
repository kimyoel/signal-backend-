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


# ──────────────────────────────────────────────
# Mock 기반 통합 테스트 — 실제 함수 호출
# ──────────────────────────────────────────────

from unittest.mock import patch, MagicMock


class _ChainableMock:
    """
    Supabase 쿼리 체이닝을 완벽히 흉내내는 헬퍼 클래스.

    왜 필요한가?
    → Supabase SDK는 .select().not_.is_().eq().lte().execute() 같이
      속성 접근(.not_)과 메서드 호출(.is_())이 섞인 체이닝을 쓴다.
      일반 MagicMock은 이 패턴을 제대로 못 따라가서
      .execute()에서 의도한 값이 안 나옴.

    해결법:
    → 어떤 속성 접근이든, 어떤 메서드 호출이든 항상 자기 자신(self)을 반환.
      오직 .execute()만 미리 지정한 결과를 반환.

    핵심 포인트:
    → .not_ 같은 속성 접근은 self를 반환 (객체)
    → .select(), .eq(), .is_() 같은 메서드 호출은 __call__로 self 반환
    → .execute()만 미리 지정한 결과 반환
    """
    def __init__(self, execute_result):
        self._execute_result = execute_result

    def __getattr__(self, name):
        # .execute()는 미리 지정한 결과를 반환하는 함수
        if name == "execute":
            return lambda: self._execute_result
        # .not_, .select, .eq, .is_, .in_, .order, .lte 등
        # 모든 속성 접근 → 자기 자신을 반환 (체이닝 유지)
        return self

    def __call__(self, *args, **kwargs):
        # .select("id"), .eq("push_enabled", True), .is_("col", "null") 등
        # 메서드로 호출될 때도 자기 자신을 반환 (체이닝 유지)
        return self


class TestGetPushRecipients:
    """get_push_recipients() — N+1 개선된 사용자 조회 테스트"""

    @patch("push_sender.supabase")
    def test_free_user_filtered_under_5m(self, mock_supabase):
        """FREE 사용자가 $500만 미만 거래에서 제외되는지"""
        from push_sender import get_push_recipients

        # users 테이블 결과
        mock_users = MagicMock()
        mock_users.data = [
            {"id": "user-1", "expo_push_token": "ExponentPushToken[aaa]", "notify_whale_min_usd": 1000000},
        ]

        # subscriptions 테이블 결과 — 구독 없음 = FREE
        mock_subs = MagicMock()
        mock_subs.data = []

        call_count = {"n": 0}

        def table_side_effect(name):
            call_count["n"] += 1
            if call_count["n"] == 1:  # users
                return _ChainableMock(mock_users)
            else:  # subscriptions
                return _ChainableMock(mock_subs)

        mock_supabase.table.side_effect = table_side_effect

        # $300만 거래 → FREE 사용자는 $500만 기준 미달 → 제외
        result = get_push_recipients(3_000_000)
        assert len(result) == 0

    @patch("push_sender.supabase")
    def test_paid_user_included_over_1m(self, mock_supabase):
        """BASIC 사용자가 $100만 이상 거래에서 포함되는지"""
        from push_sender import get_push_recipients

        mock_users = MagicMock()
        mock_users.data = [
            {"id": "user-1", "expo_push_token": "ExponentPushToken[aaa]", "notify_whale_min_usd": 1000000},
        ]

        mock_subs = MagicMock()
        mock_subs.data = [
            {"user_id": "user-1", "plan": "basic"},
        ]

        call_count = {"n": 0}

        def table_side_effect(name):
            call_count["n"] += 1
            if call_count["n"] == 1:  # users
                return _ChainableMock(mock_users)
            else:  # subscriptions
                return _ChainableMock(mock_subs)

        mock_supabase.table.side_effect = table_side_effect

        # $200만 거래 → BASIC 사용자는 $100만 기준 충족 → 포함
        result = get_push_recipients(2_000_000)
        assert len(result) == 1
        assert result[0]["plan"] == "basic"
        assert result[0]["expo_push_token"] == "ExponentPushToken[aaa]"

    @patch("push_sender.supabase")
    def test_free_user_included_over_5m(self, mock_supabase):
        """FREE 사용자도 $500만 이상이면 알림 받는지"""
        from push_sender import get_push_recipients

        mock_users = MagicMock()
        mock_users.data = [
            {"id": "user-1", "expo_push_token": "ExponentPushToken[bbb]", "notify_whale_min_usd": 1000000},
        ]

        mock_subs = MagicMock()
        mock_subs.data = []  # 구독 없음 = FREE

        call_count = {"n": 0}

        def table_side_effect(name):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _ChainableMock(mock_users)
            else:
                return _ChainableMock(mock_subs)

        mock_supabase.table.side_effect = table_side_effect

        # $600만 거래 → FREE 사용자도 $500만 기준 충족 → 포함
        result = get_push_recipients(6_000_000)
        assert len(result) == 1
        assert result[0]["plan"] == "free"

    @patch("push_sender.supabase")
    def test_mixed_users_filtering(self, mock_supabase):
        """FREE + BASIC 혼합 시, 금액 기준에 맞게 필터링되는지"""
        from push_sender import get_push_recipients

        mock_users = MagicMock()
        mock_users.data = [
            {"id": "free-user", "expo_push_token": "ExponentPushToken[free]", "notify_whale_min_usd": 1000000},
            {"id": "basic-user", "expo_push_token": "ExponentPushToken[basic]", "notify_whale_min_usd": 1000000},
        ]

        mock_subs = MagicMock()
        mock_subs.data = [
            {"user_id": "basic-user", "plan": "basic"},
            # free-user는 구독 없음 → FREE 처리
        ]

        call_count = {"n": 0}

        def table_side_effect(name):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _ChainableMock(mock_users)
            else:
                return _ChainableMock(mock_subs)

        mock_supabase.table.side_effect = table_side_effect

        # $200만 거래 → BASIC은 포함, FREE는 $500만 미달로 제외
        result = get_push_recipients(2_000_000)
        assert len(result) == 1
        assert result[0]["plan"] == "basic"

    @patch("push_sender.supabase")
    def test_no_users_returns_empty(self, mock_supabase):
        """푸시 가능한 사용자가 없을 때 빈 리스트"""
        from push_sender import get_push_recipients

        mock_users = MagicMock()
        mock_users.data = []

        mock_supabase.table.return_value = _ChainableMock(mock_users)

        result = get_push_recipients(10_000_000)
        assert result == []

    @patch("push_sender.supabase")
    def test_db_error_returns_empty(self, mock_supabase):
        """DB 에러 시 빈 리스트 반환 (죽지 않음)"""
        from push_sender import get_push_recipients

        mock_supabase.table.side_effect = Exception("DB connection failed")

        result = get_push_recipients(10_000_000)
        assert result == []


class TestSendPushBatch:
    """send_push_batch() — Expo API 호출 테스트"""

    @patch("push_sender.httpx.post")
    def test_successful_send(self, mock_post):
        """정상 발송 시 True 반환"""
        from push_sender import send_push_batch

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"status": "ok"}]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        messages = [{"to": "ExponentPushToken[aaa]", "title": "test", "body": "test"}]
        result = send_push_batch(messages)

        assert result is True
        mock_post.assert_called_once()

    @patch("push_sender.httpx.post")
    def test_api_failure_returns_false(self, mock_post):
        """Expo API 실패 시 False 반환"""
        from push_sender import send_push_batch

        mock_post.side_effect = Exception("Connection refused")

        messages = [{"to": "ExponentPushToken[aaa]", "title": "test", "body": "test"}]
        result = send_push_batch(messages)

        assert result is False

    def test_empty_messages_returns_true(self):
        """빈 메시지 리스트는 True 반환 (발송할 게 없으니까)"""
        from push_sender import send_push_batch

        result = send_push_batch([])
        assert result is True


class TestMarkPushSent:
    """mark_push_sent() — push_sent 상태 업데이트 테스트"""

    @patch("push_sender.supabase")
    def test_updates_push_sent(self, mock_supabase):
        """push_sent가 True로 업데이트 되는지"""
        from push_sender import mark_push_sent

        mark_push_sent(["uuid-1", "uuid-2"])

        # update가 2번 호출됐는지 확인
        assert mock_supabase.table.return_value.update.call_count == 2

    @patch("push_sender.supabase")
    def test_error_doesnt_crash(self, mock_supabase):
        """DB 업데이트 실패해도 에러로 죽지 않는지"""
        from push_sender import mark_push_sent

        mock_supabase.table.side_effect = Exception("DB error")

        # 에러 발생해도 예외가 밖으로 나오면 안 됨
        mark_push_sent(["uuid-1"])  # 에러 없이 통과해야 함
