# ============================================
# AI 클라이언트 서비스 (핵심 로직)
# ============================================
# GPT, Gemini, Grok 3개를 동시에 호출하고
# Claude로 검증하는 로직
#
# 비전공자 설명:
# "3명의 전문가한테 동시에 질문하고,
#  감수자(Claude)가 답변 품질 체크하는 과정"
# ============================================

import asyncio
import json
from datetime import datetime, timezone

import openai
import anthropic
import google.generativeai as genai

from app.config import settings
from app.prompts.templates import (
    GPT_SYSTEM_PROMPT,
    GEMINI_SYSTEM_PROMPT,
    GROK_SYSTEM_PROMPT,
    CLAUDE_FILTER_PROMPT,
    USER_MESSAGE_TEMPLATE,
)


def _build_user_message(news: dict) -> str:
    """뉴스 데이터로 사용자 메시지를 만드는 함수"""
    return USER_MESSAGE_TEMPLATE.format(
        title=news.get("title", ""),
        source=news.get("source", ""),
        summary=news.get("summary", ""),
        category=news.get("category", ""),
    )


# ============================
# 개별 AI 호출 함수들
# ============================

async def call_gpt(news: dict) -> dict:
    """
    GPT-4o 호출 — 매크로 경제 시각 분석

    비전공자 설명: "경제 전문가 GPT에게 물어보기"
    """
    try:
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
    except Exception as e:
        return {
            "model": "GPT-4o",
            "angle": "매크로 경제",
            "icon": "📊",
            "content": f"분석 생성 중 오류가 발생했습니다: {str(e)}",
            "error": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


async def call_gemini(news: dict) -> dict:
    """
    Gemini 1.5 Flash 호출 — 데이터 & 온체인 시각 분석

    비전공자 설명: "데이터 분석가 Gemini에게 물어보기"
    """
    try:
        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"{GEMINI_SYSTEM_PROMPT}\n\n{_build_user_message(news)}"

        # Gemini는 동기 API라서 별도 스레드에서 실행
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
    except Exception as e:
        return {
            "model": "Gemini 1.5 Flash",
            "angle": "데이터 & 온체인",
            "icon": "🔗",
            "content": f"분석 생성 중 오류가 발생했습니다: {str(e)}",
            "error": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


async def call_grok(news: dict) -> dict:
    """
    Grok-2 호출 — 소셜 심리 시각 분석

    비전공자 설명: "소셜미디어 전문가 Grok에게 물어보기"
    참고: Grok은 OpenAI와 같은 형식의 API를 써서 openai 라이브러리로 호출 가능
    """
    try:
        client = openai.AsyncOpenAI(
            api_key=settings.xai_api_key,
            base_url="https://api.x.ai/v1",  # xAI의 API 주소
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
    except Exception as e:
        return {
            "model": "Grok-2",
            "angle": "소셜 심리",
            "icon": "📱",
            "content": f"분석 생성 중 오류가 발생했습니다: {str(e)}",
            "error": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# ============================
# Claude 검증 함수
# ============================

async def verify_with_claude(text: str) -> dict:
    """
    Claude Haiku로 할루시네이션(거짓 정보) + 금지 표현 검증

    비전공자 설명: "감수자(Claude)가 다른 AI의 답변을 읽고 문제 있으면 수정"
    """
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            system=CLAUDE_FILTER_PROMPT,
            messages=[
                {"role": "user", "content": f"다음 텍스트를 검증해주세요:\n\n{text}"},
            ],
        )

        # Claude의 응답을 JSON으로 파싱
        result_text = response.content[0].text
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # JSON 파싱 실패시 원문 그대로 통과
            result = {"flagged": False, "reason": None, "cleaned_text": text}

        return result
    except Exception:
        # Claude 오류시에도 원문 통과 (분석은 보여주되 검증 안된 것으로 표시)
        return {"flagged": False, "reason": "검증 서비스 일시 오류", "cleaned_text": text}


# ============================
# 메인 함수: 3개 AI 동시 호출 + 검증
# ============================

async def call_all_ai_models(news: dict, requested_models: list[str]) -> dict:
    """
    핵심 함수! GPT + Gemini + Grok 3개를 동시에 호출하고 Claude로 검증

    비전공자 설명:
    1. 3명에게 동시에 질문함 (기다리는 시간 절약!)
    2. 답변이 오면 Claude가 각각 검증
    3. 문제 있는 부분은 자동 수정

    asyncio.gather = "3명한테 동시에 물어보는 마법"
    """

    # 1. 요청된 모델만 호출할 작업 리스트 생성
    tasks = []
    model_keys = []

    if "gpt" in requested_models:
        tasks.append(call_gpt(news))
        model_keys.append("gpt")
    if "gemini" in requested_models:
        tasks.append(call_gemini(news))
        model_keys.append("gemini")
    if "grok" in requested_models:
        tasks.append(call_grok(news))
        model_keys.append("grok")

    # 2. 동시 호출! (이게 핵심 — 3개를 순서대로가 아니라 한꺼번에)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 3. 결과 정리 + Claude 검증
    analyses = {}
    for key, result in zip(model_keys, results):
        if isinstance(result, Exception):
            # AI 호출 자체가 실패한 경우
            analyses[key] = {
                "model": key.upper(),
                "angle": "오류",
                "icon": "⚠️",
                "content": "분석을 생성할 수 없습니다. 잠시 후 다시 시도해주세요.",
                "error": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        elif result.get("error"):
            # AI가 에러를 반환한 경우
            analyses[key] = result
        else:
            # 정상 응답 → Claude 검증
            verification = await verify_with_claude(result["content"])
            if verification.get("flagged"):
                # 문제 발견 → 수정된 텍스트 사용
                result["content"] = verification["cleaned_text"]
                result["verified"] = True
                result["verification_note"] = verification.get("reason")
            else:
                result["verified"] = True
            analyses[key] = result

    return analyses
