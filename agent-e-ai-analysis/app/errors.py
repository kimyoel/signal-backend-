# ============================================
# 커스텀 에러 클래스 모음
# ============================================
# 에러 종류별로 다른 HTTP 상태 코드를 반환하기 위한 클래스
#
# 비전공자 설명:
# 에러에도 종류가 있어:
# - 401: "너 누군지 모르겠어" (인증 실패)
# - 403: "너인 건 아는데, 권한이 없어" (구독/크레딧 부족)
# - 404: "그런 거 없는데?" (뉴스 못 찾음)
# - 503: "AI가 지금 바빠서 못 해" (AI 서비스 장애)
# - 500: "나도 뭐가 잘못됐는지 모르겠어" (예상 못한 에러)
# ============================================


class SignalBaseError(Exception):
    """모든 SIGNAL 에러의 부모 클래스"""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthError(SignalBaseError):
    """
    인증 관련 에러 (401)
    - 토큰이 없거나 잘못된 경우
    - 로그인이 필요한 경우
    """

    def __init__(self, message: str = "인증이 필요합니다"):
        super().__init__(message=message, status_code=401)


class SubscriptionError(SignalBaseError):
    """
    구독/크레딧 관련 에러 (403)
    - 무료 크레딧 소진
    - 구독이 만료된 경우
    """

    def __init__(self, message: str = "AI 분석 이용권이 부족합니다"):
        super().__init__(message=message, status_code=403)


class NewsNotFoundError(SignalBaseError):
    """
    뉴스를 찾을 수 없는 에러 (404)
    - 존재하지 않는 news_id를 요청한 경우
    """

    def __init__(self, news_id: str = ""):
        message = f"해당 뉴스를 찾을 수 없습니다 (ID: {news_id})" if news_id else "해당 뉴스를 찾을 수 없습니다"
        super().__init__(message=message, status_code=404)


class AIServiceError(SignalBaseError):
    """
    AI 서비스 호출 실패 에러 (503)
    - AI API가 응답하지 않는 경우
    - 타임아웃, 네트워크 오류 등

    비전공자 설명: "GPT한테 물어봤는데 GPT가 안 받아..."
    """

    def __init__(self, model_name: str = "", reason: str = ""):
        message = f"AI 분석 서비스 일시 장애"
        if model_name:
            message += f" ({model_name})"
        if reason:
            message += f": {reason}"
        self.model_name = model_name
        self.reason = reason
        super().__init__(message=message, status_code=503)


class CacheError(SignalBaseError):
    """
    캐시 관련 에러 (비치명적 — 로깅만 하고 계속 진행)
    - 캐시 읽기/쓰기 실패
    - DB 일시 장애

    비전공자 설명: "저장된 답을 못 읽었지만, 새로 계산하면 되니까 괜찮아"
    """

    def __init__(self, message: str = "캐시 처리 중 오류가 발생했습니다"):
        super().__init__(message=message, status_code=500)


class RateLimitError(SignalBaseError):
    """
    요청 제한 에러 (429)
    - 하루 요청 한도 초과
    - Phase 3에서 적용 예정

    비전공자 설명: "너무 많이 물어봤어, 내일 다시 와"
    """

    def __init__(self, message: str = "일일 요청 한도를 초과했습니다"):
        super().__init__(message=message, status_code=429)
