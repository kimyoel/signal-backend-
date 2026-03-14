# ============================================
# 구조화된 로깅 시스템
# ============================================
# 앱에서 일어나는 모든 중요한 일을 기록하는 시스템
#
# 비전공자 설명:
# "앱의 일기장. 누가 언제 뭘 했는지, 뭐가 잘못됐는지 다 기록."
# "문제 생기면 이 일기장을 보고 원인을 찾는 거야."
#
# 출력 형식 예시 (JSON):
# {"timestamp": "2026-03-14T12:00:00", "level": "INFO",
#  "event": "ai_call_success", "model": "GPT-4o", "duration_ms": 3200}
#
# 왜 JSON? → Railway 로그 뷰어에서 검색/필터링이 쉬움
# ============================================

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """
    로그를 JSON 형태로 출력하는 포맷터

    비전공자 설명:
    - 보통 로그: "2026-03-14 ERROR 뭔가 잘못됨"
    - JSON 로그: {"timestamp": "...", "level": "ERROR", "message": "뭔가 잘못됨"}
    - JSON이 더 좋은 이유: 컴퓨터가 검색/분류하기 쉬움
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 추가 데이터가 있으면 포함 (예: model, duration_ms 등)
        if hasattr(record, "extra_data") and record.extra_data:
            log_data.update(record.extra_data)

        # 에러 정보가 있으면 포함
        if record.exc_info and record.exc_info[1]:
            log_data["error_type"] = type(record.exc_info[1]).__name__
            log_data["error_detail"] = str(record.exc_info[1])

        return json.dumps(log_data, ensure_ascii=False)


class StructuredLogger:
    """
    구조화된 로거 래퍼

    사용법:
        from app.logger import get_logger
        logger = get_logger("ai_clients")
        logger.info("GPT 호출 시작", model="GPT-4o", news_id="abc-123")
        logger.error("GPT 호출 실패", model="GPT-4o", error="timeout")
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(f"signal.{name}")

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        """추가 데이터와 함께 로그를 남기는 내부 함수"""
        record = self._logger.makeRecord(
            name=self._logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        record.extra_data = kwargs if kwargs else None
        self._logger.handle(record)

    def info(self, message: str, **kwargs: Any) -> None:
        """일반 정보 로그 (정상 동작 기록)"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """경고 로그 (잘못되진 않았지만 주의 필요)"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """에러 로그 (뭔가 잘못됨)"""
        self._log(logging.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """디버그 로그 (개발 중에만 보는 상세 정보)"""
        self._log(logging.DEBUG, message, **kwargs)


def setup_logging(level: str = "INFO") -> None:
    """
    앱 시작 시 1번 호출하는 로깅 초기화 함수

    비전공자 설명:
    "앱 켤 때 일기장 세팅하는 거. 어떤 형식으로 쓸지, 어디에 출력할지 정함."
    """
    # 루트 로거 설정
    root_logger = logging.getLogger("signal")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()

    # JSON 포맷으로 stdout(터미널)에 출력
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)


def get_logger(name: str) -> StructuredLogger:
    """
    모듈별 로거를 가져오는 함수

    사용법:
        logger = get_logger("ai_clients")  # → signal.ai_clients 로거
        logger = get_logger("auth")        # → signal.auth 로거
        logger = get_logger("cache")       # → signal.cache 로거
    """
    return StructuredLogger(name)
