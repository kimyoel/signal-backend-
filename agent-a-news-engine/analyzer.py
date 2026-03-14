# ─────────────────────────────────────────
# analyzer.py — AI 3각 분석 엔진
# 사용자가 앱에서 "AI 분석" 버튼을 누르면 이 파일의 함수가 실행됨
# ─────────────────────────────────────────
# 실행 흐름:
# 1. 캐시 확인 (이미 분석된 뉴스면 바로 반환)
# 2. 사용자 크레딧 확인 (0이면 거절)
# 3. GPT + Gemini + Grok 병렬 호출 (asyncio.gather)
# 4. Claude Haiku로 환각 검증
# 5. FAIL이면 재생성 또는 경고 태그
# 6. ai_analyses 테이블에 결과 저장
# 7. 크레딧 차감
# ─────────────────────────────────────────

import asyncio
import logging
import os

import httpx
import openai
import google.generativeai as genai
import anthropic

from db import (
    get_supabase_client,
    get_news_by_id,
    get_cached_analysis,
    save_analysis,
    update_news_has_analysis,
    get_user_credits,
    deduct_credit,
)
from prompts import (
    GPT_MACRO_PROMPT,
    GEMINI_DATA_PROMPT,
    GROK_SOCIAL_PROMPT,
    CLAUDE_VERIFY_PROMPT,
)
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("analyzer")


# ──────────────────────────────────────────
# 개별 AI 호출 함수들
# ──────────────────────────────────────────

async def call_gpt(news_title: str, news_summary: str) -> str:
    """GPT-5.4로 매크로 경제 관점 분석 호출

    - 금리, 달러, 위험자산, 유동성 관점
    - 100~150자 이내
    """
    try:
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        prompt = GPT_MACRO_PROMPT.format(
            news_title=news_title,
            news_summary=news_summary
        )
        response = await client.chat.completions.create(
            model="gpt-5.4",  # 2026-03-14 업데이트: gpt-4o → gpt-5.4 (OpenAI 최신 flagship)
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[GPT] 호출 실패: {e}")
        return f"[GPT 분석 일시 불가] {str(e)}"


async def call_gemini(news_title: str, news_summary: str) -> str:
    """Gemini 2.5 Flash로 데이터/온체인 패턴 분석 호출

    - 수치, 데이터 패턴, 지표 변화 중심
    - 100~150자 이내
    """
    try:
        api_key = os.getenv("GOOGLE_AI_API_KEY")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")  # 2026-03-14 업데이트: 2.0 deprecated → 2.5

        prompt = GEMINI_DATA_PROMPT.format(
            news_title=news_title,
            news_summary=news_summary
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"[Gemini] 호출 실패: {e}")
        return f"[Gemini 분석 일시 불가] {str(e)}"


async def call_grok(news_title: str, news_summary: str) -> str:
    """Grok 4로 소셜 센티먼트 분석 호출

    - X(트위터) 커뮤니티 반응 중심
    - 100~150자 이내
    - Grok API는 OpenAI 호환 형식 사용
    """
    try:
        api_key = os.getenv("XAI_API_KEY")
        prompt = GROK_SOCIAL_PROMPT.format(
            news_title=news_title,
            news_summary=news_summary
        )

        # Grok은 OpenAI 호환 API를 사용 (base_url만 다름)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-4",  # 2026-03-14 업데이트: grok-3 → grok-4 (xAI 최신)
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
            )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.error(f"[Grok] 호출 실패: {e}")
        return f"[Grok 분석 일시 불가] {str(e)}"


async def verify_with_claude(
    gpt_analysis: str,
    gemini_analysis: str,
    grok_analysis: str
) -> tuple[bool, str | None]:
    """Claude Haiku로 3개 분석 결과를 검증하는 함수

    확인 사항:
    - 투자 권유 표현 (매수 추천, 수익 보장, 목표가 제시)
    - 명백한 사실 오류
    - 과장/공포/탐욕 자극 표현

    Returns:
        (검증 통과 여부, 문제 내용 or None)
        예: (True, None) → 통과
        예: (False, "GPT 분석에 '매수 추천' 표현 포함") → 실패
    """
    try:
        client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        prompt = CLAUDE_VERIFY_PROMPT.format(
            gpt_analysis=gpt_analysis,
            gemini_analysis=gemini_analysis,
            grok_analysis=grok_analysis,
        )
        response = await client.messages.create(
            model="claude-3-7-sonnet-20250219",  # 2026-03-14 업데이트: haiku → claude-3-7-sonnet (검증용 경량)
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.content[0].text.strip()

        if result.startswith("PASS"):
            return True, None
        else:
            # "FAIL: 구체적 문제" 형식에서 문제 내용 추출
            note = result.replace("FAIL:", "").strip() if "FAIL:" in result else result
            return False, note

    except Exception as e:
        logger.error(f"[Claude] 검증 호출 실패: {e}")
        # Claude 실패해도 분석 결과 자체는 반환 (검증 못 한 상태로 표시)
        return False, f"검증 실패: {str(e)}"


# ──────────────────────────────────────────
# 메인 분석 함수: 위 AI들을 조합해서 실행
# ──────────────────────────────────────────

async def run_analysis(news_id: str, user_id: str) -> dict:
    """뉴스 1건에 대해 AI 3각 분석을 실행하는 메인 함수

    Args:
        news_id: 분석할 뉴스 UUID
        user_id: 요청한 사용자 UUID

    Returns:
        성공: {"success": True, "analysis_id": "...", "gpt_analysis": "...", ...}
        실패: {"success": False, "error": "...", "message": "..."}
    """
    supabase = get_supabase_client()

    # ── 1단계: 캐시 확인 ──
    cached = await get_cached_analysis(supabase, news_id)
    if cached:
        logger.info(f"[분석] 캐시 히트: news_id={news_id}")
        return {
            "success": True,
            "cached": True,
            "analysis_id": cached["id"],
            "gpt_analysis": cached["gpt_analysis"],
            "gemini_analysis": cached["gemini_analysis"],
            "grok_analysis": cached["grok_analysis"],
            "verified": cached["verified"],
            "verification_note": cached.get("verification_note"),
        }

    # ── 2단계: 크레딧 확인 ──
    credits = await get_user_credits(supabase, user_id)
    if credits == 0:
        return {
            "success": False,
            "error": "insufficient_credits",
            "message": "AI 분석 이용권이 부족합니다. 구독 플랜을 업그레이드하세요.",
        }

    # ── 3단계: 뉴스 내용 조회 ──
    news = await get_news_by_id(supabase, news_id)
    if not news:
        return {
            "success": False,
            "error": "news_not_found",
            "message": "해당 뉴스를 찾을 수 없습니다.",
        }

    news_title = news["title"]
    news_summary = news.get("summary", "")

    # ── 4단계: GPT + Gemini + Grok 병렬 호출 ──
    logger.info(f"[분석] AI 3각 호출 시작: {news_title[:30]}...")
    gpt_result, gemini_result, grok_result = await asyncio.gather(
        call_gpt(news_title, news_summary),
        call_gemini(news_title, news_summary),
        call_grok(news_title, news_summary),
        # 하나가 실패해도 나머지는 계속 진행
    )

    # ── 5단계: Claude 검증 ──
    verified, verification_note = await verify_with_claude(
        gpt_result, gemini_result, grok_result
    )

    # FAIL이면 로그만 남기고 결과는 그대로 반환 (경고 태그 포함)
    if not verified:
        logger.warning(f"[검증] FAIL: {verification_note}")

    # ── 6단계: DB 저장 ──
    analysis_data = {
        "news_id": news_id,
        "gpt_analysis": gpt_result,
        "gpt_model": "gpt-5.4",
        "gemini_analysis": gemini_result,
        "gemini_model": "gemini-2.5-flash",
        "grok_analysis": grok_result,
        "grok_model": "grok-4",
        "verified": verified,
        "verification_note": verification_note,
    }

    saved = await save_analysis(supabase, analysis_data)
    await update_news_has_analysis(supabase, news_id)

    # ── 7단계: 크레딧 차감 (FREE 사용자만) ──
    await deduct_credit(supabase, user_id)

    logger.info(f"[분석] 완료: news_id={news_id}, verified={verified}")

    return {
        "success": True,
        "cached": False,
        "analysis_id": saved.get("id", ""),
        "gpt_analysis": gpt_result,
        "gemini_analysis": gemini_result,
        "grok_analysis": grok_result,
        "verified": verified,
        "verification_note": verification_note,
    }

