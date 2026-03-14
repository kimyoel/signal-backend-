# ============================================
# 재시도 & 타임아웃 유틸리티
# ============================================
# AI 호출이 느리거나 실패했을 때 자동으로 다시 시도하는 도구
#
# 비전공자 설명:
# "전화했는데 안 받아? → 15초 기다려보고 → 한 번만 더 걸어봐"
# "그래도 안 받으면 포기하고 에러 메시지 남기기"
# ============================================

import asyncio
from functools import wraps
from typing import TypeVar, Callable, Any

T = TypeVar("T")

# 기본 설정값
DEFAULT_TIMEOUT_SECONDS = 15    # AI 응답 최대 대기 시간 (15초)
DEFAULT_MAX_RETRIES = 1         # 실패 시 재시도 횟수 (1번)
DEFAULT_RETRY_DELAY_SECONDS = 1 # 재시도 전 대기 시간 (1초)


async def with_timeout_and_retry(
    func: Callable,
    *args,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS,
    operation_name: str = "작업",
    **kwargs,
) -> Any:
    """
    비동기 함수에 타임아웃 + 재시도를 적용하는 유틸리티

    사용법:
        result = await with_timeout_and_retry(
            call_gpt, news,
            timeout=15,
            max_retries=1,
            operation_name="GPT-4o 호출"
        )

    동작 흐름:
    1. func()를 호출하고 timeout초 안에 응답이 오는지 확인
    2. 타임아웃이나 에러 발생 시 → retry_delay초 기다린 후 재시도
    3. max_retries번까지 재시도
    4. 그래도 실패하면 → TimeoutError 또는 원래 에러를 올림

    비전공자 설명:
    - timeout: "15초 안에 대답 안 하면 끊어"
    - max_retries: "실패하면 1번 더 시도해봐"
    - retry_delay: "재시도 전에 1초 쉬어"
    """

    last_error = None

    # 총 시도 횟수 = 첫 시도(1) + 재시도(max_retries)
    for attempt in range(1 + max_retries):
        try:
            # asyncio.wait_for = "이 함수를 timeout초 안에 끝내라"
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout,
            )
            return result

        except asyncio.TimeoutError:
            last_error = TimeoutError(
                f"{operation_name} 타임아웃: {timeout}초 초과 "
                f"(시도 {attempt + 1}/{1 + max_retries})"
            )

        except Exception as e:
            last_error = e

        # 마지막 시도가 아니면 잠깐 기다렸다가 재시도
        if attempt < max_retries:
            await asyncio.sleep(retry_delay)

    # 모든 시도 실패 → 마지막 에러를 올림
    raise last_error
