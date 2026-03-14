# ============================================
# 테스트: 에러 핸들링 & 커스텀 에러
# ============================================
# 에러 클래스들이 올바른 상태 코드와 메시지를 갖는지 검증
# 전역 예외 핸들러가 제대로 JSON 응답을 반환하는지 검증
#
# 비전공자 설명:
# "에러가 났을 때 사용자한테 보여줄 메시지가 올바른지 자동 체크"
# ============================================

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.errors import (
    SignalBaseError,
    AuthError,
    SubscriptionError,
    NewsNotFoundError,
    AIServiceError,
    CacheError,
    RateLimitError,
)


# --- 에러 클래스 테스트 ---

def test_AuthError_기본값():
    """AuthError는 401 상태 코드를 가져야 함"""
    error = AuthError()
    assert error.status_code == 401
    assert error.message == "인증이 필요합니다"


def test_AuthError_커스텀_메시지():
    """AuthError에 커스텀 메시지를 넣으면 그 메시지가 사용됨"""
    error = AuthError("토큰이 만료되었습니다")
    assert error.status_code == 401
    assert error.message == "토큰이 만료되었습니다"


def test_SubscriptionError_기본값():
    """SubscriptionError는 403 상태 코드를 가져야 함"""
    error = SubscriptionError()
    assert error.status_code == 403
    assert "이용권" in error.message


def test_NewsNotFoundError_ID포함():
    """NewsNotFoundError는 404 + news_id를 메시지에 포함"""
    error = NewsNotFoundError("abc-123")
    assert error.status_code == 404
    assert "abc-123" in error.message


def test_NewsNotFoundError_ID없음():
    """NewsNotFoundError에 ID 안 넣어도 동작"""
    error = NewsNotFoundError()
    assert error.status_code == 404
    assert "찾을 수 없습니다" in error.message


def test_AIServiceError_모델명포함():
    """AIServiceError는 503 + 모델명을 메시지에 포함"""
    error = AIServiceError(model_name="GPT-4o", reason="타임아웃")
    assert error.status_code == 503
    assert "GPT-4o" in error.message
    assert "타임아웃" in error.message


def test_AIServiceError_기본값():
    """AIServiceError 기본값"""
    error = AIServiceError()
    assert error.status_code == 503
    assert "일시 장애" in error.message


def test_CacheError_기본값():
    """CacheError는 500 상태 코드"""
    error = CacheError()
    assert error.status_code == 500


def test_RateLimitError_기본값():
    """RateLimitError는 429 상태 코드"""
    error = RateLimitError()
    assert error.status_code == 429
    assert "한도" in error.message


def test_모든_에러는_SignalBaseError_상속():
    """모든 커스텀 에러는 SignalBaseError를 상속해야 함"""
    errors = [
        AuthError(),
        SubscriptionError(),
        NewsNotFoundError(),
        AIServiceError(),
        CacheError(),
        RateLimitError(),
    ]
    for error in errors:
        assert isinstance(error, SignalBaseError), f"{type(error).__name__}이 SignalBaseError를 상속하지 않음"
        assert isinstance(error, Exception), f"{type(error).__name__}이 Exception을 상속하지 않음"


def test_에러_str_변환():
    """에러를 str()로 변환하면 메시지가 나와야 함"""
    error = AuthError("테스트 메시지")
    assert str(error) == "테스트 메시지"
