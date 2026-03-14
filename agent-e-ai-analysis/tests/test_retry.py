# ============================================
# 테스트: 타임아웃 & 재시도 유틸리티
# ============================================
# retry.py의 with_timeout_and_retry 함수가 제대로 작동하는지 검증
#
# 비전공자 설명:
# "타임아웃이 진짜 걸리는지, 재시도가 진짜 되는지 자동으로 확인"
# ============================================

import asyncio
import pytest
import sys
import os

# 프로젝트 루트를 Python 경로에 추가 (import가 되게)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.retry import with_timeout_and_retry


# --- 테스트용 가짜 함수들 ---

async def fast_function():
    """즉시 성공하는 함수 (0.1초)"""
    await asyncio.sleep(0.1)
    return "성공!"


async def slow_function():
    """느린 함수 (100초 — 타임아웃 걸려야 함)"""
    await asyncio.sleep(100)
    return "이건 안 와야 함"


call_count = 0  # 호출 횟수 추적용


async def fail_once_then_succeed():
    """첫 번째는 실패, 두 번째는 성공하는 함수 (재시도 테스트용)"""
    global call_count
    call_count += 1
    if call_count == 1:
        raise ConnectionError("첫 번째 시도 실패!")
    return "재시도 성공!"


async def always_fail():
    """항상 실패하는 함수"""
    raise ValueError("항상 실패!")


# --- 테스트 케이스들 ---

@pytest.mark.asyncio
async def test_정상_호출_성공():
    """빠른 함수는 타임아웃 없이 정상 반환"""
    result = await with_timeout_and_retry(
        fast_function,
        timeout=5,
        max_retries=0,
        operation_name="빠른 함수",
    )
    assert result == "성공!"


@pytest.mark.asyncio
async def test_타임아웃_발생():
    """느린 함수는 타임아웃으로 TimeoutError 발생"""
    with pytest.raises(TimeoutError):
        await with_timeout_and_retry(
            slow_function,
            timeout=0.5,  # 0.5초 타임아웃 (테스트라서 짧게)
            max_retries=0,  # 재시도 없음
            operation_name="느린 함수",
        )


@pytest.mark.asyncio
async def test_타임아웃_재시도_후에도_실패():
    """느린 함수 + 재시도 1회 → 그래도 타임아웃"""
    with pytest.raises(TimeoutError):
        await with_timeout_and_retry(
            slow_function,
            timeout=0.3,
            max_retries=1,
            retry_delay=0.1,
            operation_name="느린 함수 재시도",
        )


@pytest.mark.asyncio
async def test_재시도로_성공():
    """첫 번째 실패 → 두 번째 성공"""
    global call_count
    call_count = 0  # 카운터 리셋

    result = await with_timeout_and_retry(
        fail_once_then_succeed,
        timeout=5,
        max_retries=1,
        retry_delay=0.1,
        operation_name="재시도 함수",
    )
    assert result == "재시도 성공!"
    assert call_count == 2  # 2번 호출됨 (1번 실패 + 1번 성공)


@pytest.mark.asyncio
async def test_재시도_불가_항상_실패():
    """항상 실패하는 함수 → 재시도해도 실패"""
    with pytest.raises(ValueError, match="항상 실패"):
        await with_timeout_and_retry(
            always_fail,
            timeout=5,
            max_retries=2,
            retry_delay=0.1,
            operation_name="항상 실패 함수",
        )


@pytest.mark.asyncio
async def test_인자_전달():
    """함수에 인자가 전달되는지 확인"""

    async def add(a, b):
        return a + b

    result = await with_timeout_and_retry(
        add, 3, 7,
        timeout=5,
        max_retries=0,
        operation_name="덧셈 함수",
    )
    assert result == 10
