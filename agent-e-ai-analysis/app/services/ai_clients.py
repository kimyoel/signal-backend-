# ============================================
# AI 클라이언트 서비스 (핵심 로직)
# ============================================
# GPT, Gemini, Grok 3개를 동시에 호출하고
# Claude로 검증하는 로직
#
# 비전공자 설명:
# "3명의 전문가한테 동시에 질문하고,
#  감수자(Claude)가 답변 품질 체크하는 과정"
#
# [v1.1] 에러 핸들링 강화
# - 각 AI 호출에 15초 타임아웃
# - 실패 시 1회 자동 재시도
# - 1개 AI가 죽어도 나머지는 정상 반환 (실패 격리)
# ============================================

import asyncio
import json
from datetime import datetime, timezone

import openai
import anthropic
import google.generativeai as genai

from app.config import settings
from app.errors import AIServiceError
from app.services.retry import with_timeout_and_retry
from app.prompts.templates import (
    GPT_SYSTEM_PROMPT,
    GEMINI_SYSTEM_PROMPT,
    GROK_SYSTEM_PROMPT,
    CLAUDE_FILTER_PROMPT,
    USER_MESSAGE_TEMPLATE,
)

# --- 타임아웃 설정 ---
AI_CALL_TIMEOUT = 15       # AI 호출 최대 대기 시간 (초)
AI_CALL_MAX_RETRIES = 1    # 실패 시 재시도 횟수
CLAUDE_TIMEOUT = 10        # Claude 검증은 좀 더 짧게 (초)


def _build_user_message(news: dict) -> str:
    """뉴스 데이터로 사용자 메시지를 만드는 함수"""
    return USER_MESSAGE_TEMPLATE.format(
        title=news.get("title", ""),
        source=news.get("source", ""),
        summary=news.get("summary", ""),
        category=news.get("category", ""),
    )


def _make_error_result(model: str, angle: str, icon: str, reason: str) -> dict:
    """
    AI 호출 실패 시 통일된 에러 응답을 만드는 헬퍼 함수

    비전공자 설명: "에러 났을 때 보여줄 메시지를 깔끔하게 만드는 틀"
    """
    return {
        "model": model,
        "angle": angle,
        "icon": icon,
        "content": f"일시적으로 분석을 생성할 수 없습니다. ({reason})",
        "error": True,
        "verified": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================
# 개별 AI 호출 함수들 (순수 호출 로직)
# ============================
# 아래 함수들은 "AI한테 물어보는 것"만 담당.
# 타임아웃/재시도는 call_all_ai_models()에서 처리.

async def _raw_call_gpt(news: dict) -> dict:
    """
    GPT-4o 호출 — 매크로 경제 시각 분석 (순수 호출)

    비전공자 설명: "경제 전문가 GPT에게 물어보기"
    """
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": GPT_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(news)},
        ],
        max_tokens=settings.max_tokens_per_model,
    )
    return {
        "model": "GPT-4o",
        "angle": "매크로 경제",
        "icon": "📊",
        "content": response.choices[0].message.content,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _raw_call_gemini(news: dict) -> dict:
    """
    Gemini 1.5 Flash 호출 — 데이터 & 온체인 시각 분석 (순수 호출)

    비전공자 설명: "데이터 분석가 Gemini에게 물어보기"
    """
    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"{GEMINI_SYSTEM_PROMPT}\n\n{_build_user_message(news)}"

    # Gemini는 동기 API → 별도 스레드에서 실행해야 다른 AI를 안 막음
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(prompt),
    )

    return {
        "model": "Gemini 1.5 Flash",
        "angle": "데이터 & 온체인",
        "icon": "🔗",
        "content": response.text,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _raw_call_grok(news: dict) -> dict:
    """
    Grok-2 호출 — 소셜 심리 시각 분석 (순수 호출)

    비전공자 설명: "소셜미디어 전문가 Grok에게 물어보기"
    참고: Grok은 OpenAI와 같은 형식의 API를 쓰므로 openai 라이브러리로 호출
    """
    client = openai.AsyncOpenAI(
        api_key=settings.xai_api_key,
        base_url="https://api.x.ai/v1",
    )
    response = await client.chat.completions.create(
        model="grok-2",
        messages=[
            {"role": "system", "content": GROK_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(news)},
        ],
        max_tokens=settings.max_tokens_per_model,
    )
    return {
        "model": "Grok-2",
        "angle": "소셜 심리",
        "icon": "📱",
        "content": response.choices[0].message.content,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================
# 안전한 AI 호출 래퍼 (타임아웃 + 재시도 + 실패 격리)
# ============================
# 비전공자 설명:
# "각 AI를 부를 때 보호막을 씌우는 것"
# - 15초 안에 안 오면 끊고
# - 한 번 더 시도해보고
# - 그래도 안 되면 에러 메시지만 남기고 넘어감

async def _safe_call(
    raw_func,
    news: dict,
    model_name: str,
    angle: str,
    icon: str,
) -> dict:
    """
    개별 AI 호출을 타임아웃 + 재시도로 감싸는 안전 래퍼

    핵심: 이 함수는 절대 Exception을 raise하지 않음!
    → 성공이든 실패든 항상 dict를 반환
    → 이래야 1개 AI가 죽어도 나머지에 영향 없음 (실패 격리)
    """
    try:
        result = await with_timeout_and_retry(
            raw_func,
            news,
            timeout=AI_CALL_TIMEOUT,
            max_retries=AI_CALL_MAX_RETRIES,
            operation_name=f"{model_name} 호출",
        )
        return result

    except TimeoutError:
        # 15초 × 2번 = 30초 기다렸는데 안 옴
        return _make_error_result(model_name, angle, icon, "응답 시간 초과")

    except Exception as e:
        # 네트워크 오류, API 키 오류 등
        error_type = type(e).__name__
        return _make_error_result(model_name, angle, icon, f"{error_type}")


# ============================
# Claude 검증 함수 (타임아웃 적용)
# ============================

async def _raw_verify_with_claude(text: str) -> dict:
    """Claude Haiku로 할루시네이션 + 금지 표현 검증 (순수 호출)"""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1000,
        system=CLAUDE_FILTER_PROMPT,
        messages=[
            {"role": "user", "content": f"다음 텍스트를 검증해주세요:\n\n{text}"},
        ],
    )

    result_text = response.content[0].text
    try:
        result = json.loads(result_text)
    except json.JSONDecodeError:
        result = {"flagged": False, "reason": None, "cleaned_text": text}

    return result


async def verify_with_claude(text: str) -> dict:
    """
    Claude Haiku 검증 (타임아웃 + 재시도 적용)

    비전공자 설명:
    "감수자한테 10초 안에 검토해달라고 함.
     안 되면 한 번 더 부탁하고,
     그래도 안 되면 검증 없이 그냥 통과시킴"
    
    중요: Claude 검증 실패해도 분석 자체는 보여줌! (비치명적 에러)
    """
    try:
        result = await with_timeout_and_retry(
            _raw_verify_with_claude,
            text,
            timeout=CLAUDE_TIMEOUT,
            max_retries=AI_CALL_MAX_RETRIES,
            operation_name="Claude 검증",
        )
        return result

    except Exception:
        # Claude가 실패해도 → 원문 그대로 통과 (검증 안된 것으로 표시)
        return {
            "flagged": False,
            "reason": "검증 서비스 일시 오류",
            "cleaned_text": text,
        }


# ============================
# 메인 함수: 3개 AI 동시 호출 + 검증
# ============================

async def call_all_ai_models(news: dict, requested_models: list[str]) -> dict:
    """
    핵심 함수! GPT + Gemini + Grok 3개를 동시에 호출하고 Claude로 검증

    비전공자 설명:
    1. 3명에게 동시에 질문 (기다리는 시간 절약!)
    2. 각각 15초 타임아웃 + 1회 재시도 (보호막)
    3. 1명이 실패해도 나머지 2명 답변은 정상 반환 (실패 격리)
    4. 정상 답변은 Claude가 검증
    5. 문제 있는 부분만 자동 수정

    [변경점 v1.1]
    - 이전: try-except로 에러만 잡았음
    - 지금: 타임아웃 15초 + 재시도 1회 + _safe_call로 완전 격리
    """

    # --- AI 호출 정보 매핑 ---
    model_map = {
        "gpt": {
            "func": _raw_call_gpt,
            "model_name": "GPT-4o",
            "angle": "매크로 경제",
            "icon": "📊",
        },
        "gemini": {
            "func": _raw_call_gemini,
            "model_name": "Gemini 1.5 Flash",
            "angle": "데이터 & 온체인",
            "icon": "🔗",
        },
        "grok": {
            "func": _raw_call_grok,
            "model_name": "Grok-2",
            "angle": "소셜 심리",
            "icon": "📱",
        },
    }

    # 1. 요청된 모델만 _safe_call로 감싸서 태스크 생성
    tasks = []
    model_keys = []

    for key in requested_models:
        if key in model_map:
            info = model_map[key]
            tasks.append(
                _safe_call(
                    raw_func=info["func"],
                    news=news,
                    model_name=info["model_name"],
                    angle=info["angle"],
                    icon=info["icon"],
                )
            )
            model_keys.append(key)

    # 2. 동시 호출! (_safe_call 덕분에 여기서 Exception이 나올 일 없음)
    results = await asyncio.gather(*tasks)

    # 3. 결과 정리 + Claude 검증
    analyses = {}
    for key, result in zip(model_keys, results):
        if result.get("error"):
            # AI가 실패한 경우 → 에러 결과 그대로 사용
            analyses[key] = result
        else:
            # 정상 응답 → Claude 검증
            verification = await verify_with_claude(result["content"])
            if verification.get("flagged"):
                result["content"] = verification["cleaned_text"]
                result["verified"] = True
                result["verification_note"] = verification.get("reason")
            else:
                result["verified"] = True
            analyses[key] = result

    return analyses
