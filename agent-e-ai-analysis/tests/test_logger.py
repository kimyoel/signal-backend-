# ============================================
# 로깅 시스템 테스트
# ============================================
# 비전공자 설명:
# "일기장(로거)이 제대로 작동하는지 테스트"
# - JSON 형식으로 출력되는지
# - 추가 데이터(model, duration_ms 등)가 포함되는지
# - 에러 정보가 로그에 남는지
# ============================================

import json
import logging
import pytest

from app.logger import JsonFormatter, StructuredLogger, setup_logging, get_logger


class TestJsonFormatter:
    """JSON 포맷터 테스트"""

    def test_기본_로그_JSON_형식_출력(self):
        """기본 로그가 JSON 형식으로 출력되는지"""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="signal.test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="테스트 메시지",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)

        # JSON으로 파싱 가능해야 함
        parsed = json.loads(result)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "signal.test"
        assert parsed["message"] == "테스트 메시지"
        assert "timestamp" in parsed

    def test_추가_데이터_포함(self):
        """extra_data가 있으면 JSON에 포함되는지"""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="signal.test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="AI 호출 성공",
            args=(),
            exc_info=None,
        )
        # extra_data 추가 (StructuredLogger가 하는 것처럼)
        record.extra_data = {"model": "GPT-4o", "duration_ms": 3200}
        result = formatter.format(record)

        parsed = json.loads(result)
        assert parsed["model"] == "GPT-4o"
        assert parsed["duration_ms"] == 3200

    def test_extra_data_없으면_기본만_출력(self):
        """extra_data가 없으면 기본 필드만 나오는지"""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="signal.test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="경고입니다",
            args=(),
            exc_info=None,
        )
        # extra_data 없음
        result = formatter.format(record)

        parsed = json.loads(result)
        assert parsed["level"] == "WARNING"
        assert "model" not in parsed  # 추가 데이터 없어야 함

    def test_에러_정보_포함(self):
        """에러가 발생하면 에러 타입과 상세 정보가 로그에 남는지"""
        formatter = JsonFormatter()
        try:
            raise ValueError("테스트 에러")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="signal.test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="에러 발생",
            args=(),
            exc_info=exc_info,
        )
        result = formatter.format(record)

        parsed = json.loads(result)
        assert parsed["error_type"] == "ValueError"
        assert "테스트 에러" in parsed["error_detail"]


class TestStructuredLogger:
    """구조화된 로거 테스트"""

    def _capture_log(self, logger_name: str, level: str = "DEBUG"):
        """
        로그 출력을 캡처하기 위한 헬퍼
        
        비전공자 설명:
        "pytest가 stdout을 가로채서 capsys로 못 잡는 문제가 있음.
         그래서 직접 StringIO로 핸들러를 붙여서 캡처하는 방식."
        """
        import io
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        log = get_logger(logger_name)
        log._logger.addHandler(handler)
        log._logger.setLevel(getattr(logging, level.upper()))
        return log, stream, handler

    def _cleanup(self, log, handler):
        """테스트 후 핸들러 정리"""
        log._logger.removeHandler(handler)

    def test_info_로그_출력(self):
        """info 레벨 로그가 정상 출력되는지"""
        log, stream, handler = self._capture_log("test_info")
        log.info("정상 동작", key="value")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "정상 동작"
        assert parsed["key"] == "value"
        self._cleanup(log, handler)

    def test_warning_로그_출력(self):
        """warning 레벨 로그가 정상 출력되는지"""
        log, stream, handler = self._capture_log("test_warning")
        log.warning("주의 필요", reason="테스트")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["level"] == "WARNING"
        assert parsed["reason"] == "테스트"
        self._cleanup(log, handler)

    def test_error_로그_출력(self):
        """error 레벨 로그가 정상 출력되는지"""
        log, stream, handler = self._capture_log("test_error")
        log.error("실패!", error_type="TimeoutError")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["level"] == "ERROR"
        assert parsed["error_type"] == "TimeoutError"
        self._cleanup(log, handler)

    def test_debug_로그_DEBUG_레벨에서만_출력(self):
        """DEBUG 레벨일 때 debug 로그가 나오는지"""
        log, stream, handler = self._capture_log("test_debug")
        log.debug("디버그 정보", detail="상세")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["level"] == "DEBUG"
        assert parsed["detail"] == "상세"
        self._cleanup(log, handler)

    def test_여러_키워드_인자_동시_전달(self):
        """여러 키워드 인자가 한번에 잘 들어가는지"""
        log, stream, handler = self._capture_log("test_multi")
        log.info(
            "AI 호출 완료",
            model="GPT-4o",
            duration_ms=2500,
            news_id="abc-123",
            success=True,
        )

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["model"] == "GPT-4o"
        assert parsed["duration_ms"] == 2500
        assert parsed["news_id"] == "abc-123"
        assert parsed["success"] is True
        self._cleanup(log, handler)


class TestGetLogger:
    """get_logger 함수 테스트"""

    def test_로거_이름_prefix(self):
        """get_logger가 signal. 접두사를 붙이는지"""
        log = get_logger("ai_clients")
        assert log._logger.name == "signal.ai_clients"

    def test_다른_이름의_로거_생성(self):
        """다른 이름으로 여러 로거를 만들 수 있는지"""
        log1 = get_logger("auth")
        log2 = get_logger("cache")
        assert log1._logger.name != log2._logger.name


class TestSetupLogging:
    """setup_logging 함수 테스트"""

    def test_로깅_초기화_INFO_레벨(self):
        """INFO 레벨로 초기화되는지"""
        setup_logging("INFO")
        root = logging.getLogger("signal")
        assert root.level == logging.INFO

    def test_로깅_초기화_DEBUG_레벨(self):
        """DEBUG 레벨로 초기화되는지"""
        setup_logging("DEBUG")
        root = logging.getLogger("signal")
        assert root.level == logging.DEBUG

    def test_핸들러_중복_방지(self):
        """setup_logging을 여러 번 호출해도 핸들러가 중복되지 않는지"""
        setup_logging("INFO")
        setup_logging("INFO")
        setup_logging("INFO")
        root = logging.getLogger("signal")
        assert len(root.handlers) == 1  # 항상 1개만!
