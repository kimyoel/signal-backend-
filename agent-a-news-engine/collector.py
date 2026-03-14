# ─────────────────────────────────────────
# collector.py — 뉴스 수집 + 채점 + DB 저장
# 30분마다 APScheduler가 이 파일의 함수를 호출함
# ─────────────────────────────────────────
# 실행 흐름:
# 1. analyst_sources에서 활성 소스 목록 로드
# 2. 각 소스에서 뉴스 수집 (RSS: feedparser, NewsAPI: httpx)
# 3. source_url 기준 중복 제거
# 4. Gemini Flash-Lite로 중요도 1~5 채점
# 5. 중요도 3 이상만 남기기
# 6. Gemini Flash로 한국어 번역 + 요약
# 7. news 테이블에 저장
# 8. 중요도 5는 posted_to_threads=false로 저장 (에이전트 C용)
# ─────────────────────────────────────────

import asyncio
import json
import logging
from datetime import datetime, timezone

import feedparser
import httpx
import google.generativeai as genai

from db import (
    get_supabase_client,
    check_duplicate_url,
    save_news_batch,
)
from sources import load_rss_sources, NEWSAPI_KEYWORDS
from prompts import SCORING_PROMPT, TRANSLATE_SUMMARIZE_PROMPT

import os
from dotenv import load_dotenv

load_dotenv()

# 로거 설정
logger = logging.getLogger("collector")


# ──────────────────────────────────────────
# 1단계: RSS 피드에서 뉴스 수집
# ──────────────────────────────────────────

async def fetch_rss_feed(source: dict) -> list[dict]:
    """하나의 RSS 피드에서 뉴스 항목들을 가져오는 함수

    Args:
        source: analyst_sources 테이블의 한 행
               {"name": "Reuters", "source_url": "https://...", "category": "macro"}

    Returns:
        파싱된 뉴스 목록 [{"title": "...", "link": "...", "published": "...", ...}]
    """
    try:
        # httpx로 RSS XML을 가져온 뒤 feedparser로 파싱
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(source["source_url"])
            feed = feedparser.parse(response.text)

        news_items = []
        for entry in feed.entries[:10]:  # 피드당 최대 10개
            news_items.append({
                "title_original": entry.get("title", ""),
                "source_url": entry.get("link", ""),
                "source": source["name"],
                "category": source["category"],
                # feedparser가 파싱한 발행 시각 (없으면 현재 시각)
                "published_at": entry.get("published", datetime.now(timezone.utc).isoformat()),
                # 내용 미리보기 (채점용) — 첫 200자
                "content_preview": entry.get("summary", "")[:200],
            })

        logger.info(f"[RSS] {source['name']}: {len(news_items)}개 수집")
        return news_items

    except Exception as e:
        logger.error(f"[RSS] {source['name']} 수집 실패: {e}")
        return []


async def fetch_newsapi() -> list[dict]:
    """NewsAPI에서 키워드 기반으로 뉴스를 수집하는 함수

    Returns:
        파싱된 뉴스 목록
    """
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        logger.warning("[NewsAPI] API 키가 설정되지 않았습니다. 건너뜀.")
        return []

    news_items = []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for keyword in NEWSAPI_KEYWORDS[:5]:  # 키워드 5개만 (API 한도 절약)
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": keyword,
                    "sortBy": "publishedAt",
                    "pageSize": 5,  # 키워드당 5개
                    "apiKey": api_key,
                    "language": "en",
                }
                response = await client.get(url, params=params)
                data = response.json()

                for article in data.get("articles", []):
                    news_items.append({
                        "title_original": article.get("title", ""),
                        "source_url": article.get("url", ""),
                        "source": article.get("source", {}).get("name", "NewsAPI"),
                        "category": "macro",  # NewsAPI는 기본 macro로 분류
                        "published_at": article.get("publishedAt", datetime.now(timezone.utc).isoformat()),
                        "content_preview": (article.get("description") or "")[:200],
                        "image_url": article.get("urlToImage"),
                    })

        logger.info(f"[NewsAPI] 총 {len(news_items)}개 수집")

    except Exception as e:
        logger.error(f"[NewsAPI] 수집 실패: {e}")

    return news_items


# ──────────────────────────────────────────
# 2단계: 중복 제거
# ──────────────────────────────────────────

async def remove_duplicates(news_items: list[dict]) -> list[dict]:
    """이미 DB에 있는 뉴스를 제거하는 함수 (source_url 기준)"""
    supabase = get_supabase_client()
    unique_items = []

    for item in news_items:
        if not item.get("source_url"):
            continue
        is_dup = await check_duplicate_url(supabase, item["source_url"])
        if not is_dup:
            unique_items.append(item)

    logger.info(f"[중복제거] {len(news_items)}개 → {len(unique_items)}개 (중복 {len(news_items) - len(unique_items)}개 제거)")
    return unique_items


# ──────────────────────────────────────────
# 3단계: Gemini Flash-Lite로 중요도 채점
# ──────────────────────────────────────────

async def score_importance(news_items: list[dict]) -> list[dict]:
    """Gemini Flash-Lite로 각 뉴스의 중요도 1~5를 채점하는 함수

    - 배치로 처리 (한 번에 여러 개)
    - 채점 결과를 news_items 각 항목에 "importance" 키로 추가
    """
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        logger.warning("[채점] Google AI API 키 없음. 모두 중요도 3으로 기본 설정.")
        for item in news_items:
            item["importance"] = 3
        return news_items

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash-lite")

    for item in news_items:
        try:
            prompt = SCORING_PROMPT.format(
                title=item["title_original"],
                content_preview=item.get("content_preview", "")
            )
            response = model.generate_content(prompt)
            # 응답에서 숫자만 추출 (1~5)
            score_text = response.text.strip()
            score = int(score_text) if score_text.isdigit() else 3
            item["importance"] = max(1, min(5, score))  # 1~5 범위 강제
        except Exception as e:
            logger.error(f"[채점] 실패: {item['title_original'][:30]}... → 기본 3 적용. 에러: {e}")
            item["importance"] = 3

    logger.info(f"[채점] {len(news_items)}개 완료")
    return news_items


# ──────────────────────────────────────────
# 4단계: 중요도 3 미만 필터링
# ──────────────────────────────────────────

def filter_by_importance(news_items: list[dict], min_importance: int = 3) -> list[dict]:
    """중요도가 min_importance 미만인 뉴스를 버리는 함수"""
    filtered = [item for item in news_items if item.get("importance", 0) >= min_importance]
    logger.info(f"[필터] 중요도 {min_importance}+ 필터: {len(news_items)}개 → {len(filtered)}개")
    return filtered


# ──────────────────────────────────────────
# 5단계: Gemini Flash로 한국어 번역 + 요약
# ──────────────────────────────────────────

async def translate_and_summarize(news_items: list[dict]) -> list[dict]:
    """영문 뉴스를 한국어로 번역하고 1~2문장 요약하는 함수

    - Gemini Flash 사용
    - 이미 한국어인 뉴스는 요약만 수행
    """
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        logger.warning("[번역] Google AI API 키 없음. 원문 그대로 사용.")
        for item in news_items:
            item["title"] = item["title_original"]
            item["summary"] = item.get("content_preview", "")[:100]
        return news_items

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    for item in news_items:
        try:
            prompt = TRANSLATE_SUMMARIZE_PROMPT.format(
                title=item["title_original"],
                content=item.get("content_preview", "")
            )
            response = model.generate_content(prompt)
            # JSON 파싱 시도
            result_text = response.text.strip()

            # JSON 블록에서 추출 (```json ... ``` 감싸는 경우 대비)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)
            item["title"] = result.get("title_ko", item["title_original"])
            item["summary"] = result.get("summary_ko", "")

        except Exception as e:
            logger.error(f"[번역] 실패: {item['title_original'][:30]}... 에러: {e}")
            item["title"] = item["title_original"]
            item["summary"] = item.get("content_preview", "")[:100]

    logger.info(f"[번역] {len(news_items)}개 완료")
    return news_items


# ──────────────────────────────────────────
# 6단계: DB 저장
# ──────────────────────────────────────────

async def save_to_db(news_items: list[dict]) -> list[dict]:
    """가공된 뉴스를 Supabase news 테이블에 저장하는 함수

    - DB 스키마(01_db_schema.md) 컬럼명과 정확히 일치하는 형태로 변환
    - 중요도 5 뉴스는 posted_to_threads=false로 저장 (에이전트 C가 감지)
    """
    supabase = get_supabase_client()

    # DB 스키마에 맞게 데이터 정리
    db_records = []
    for item in news_items:
        record = {
            "title": item.get("title", item["title_original"]),
            "title_original": item["title_original"],
            "summary": item.get("summary", ""),
            "source": item["source"],
            "source_url": item["source_url"],
            "category": item["category"],
            "importance": item["importance"],
            "published_at": item["published_at"],
            "image_url": item.get("image_url"),
            # 중요도 5면 Threads 포스팅 대기 상태로
            "posted_to_threads": False if item["importance"] == 5 else None,
        }
        db_records.append(record)

    saved = await save_news_batch(supabase, db_records)
    logger.info(f"[저장] {len(saved)}개 DB 저장 완료")
    return saved


# ──────────────────────────────────────────
# 메인 파이프라인: 위 단계를 순서대로 실행
# ──────────────────────────────────────────

async def run_collection_pipeline():
    """뉴스 수집 전체 파이프라인 (30분마다 실행)

    1. RSS + NewsAPI에서 뉴스 수집
    2. 중복 제거
    3. 중요도 채점 (Gemini Flash-Lite)
    4. 중요도 3 미만 필터링
    5. 한국어 번역 + 요약 (Gemini Flash)
    6. DB 저장
    """
    logger.info("=" * 50)
    logger.info("[파이프라인] 뉴스 수집 시작")
    logger.info("=" * 50)

    # 1. 소스에서 뉴스 수집 (RSS + NewsAPI 병렬)
    rss_sources = await load_rss_sources()
    rss_tasks = [fetch_rss_feed(source) for source in rss_sources if source["source_type"] == "rss"]
    rss_results = await asyncio.gather(*rss_tasks, return_exceptions=True)

    # RSS 결과 합치기 (에러가 아닌 것만)
    all_news = []
    for result in rss_results:
        if isinstance(result, list):
            all_news.extend(result)

    # NewsAPI 뉴스도 추가
    newsapi_news = await fetch_newsapi()
    all_news.extend(newsapi_news)

    logger.info(f"[수집] 총 {len(all_news)}개 수집")

    if not all_news:
        logger.info("[파이프라인] 수집된 뉴스 없음. 종료.")
        return

    # 2. 중복 제거
    unique_news = await remove_duplicates(all_news)
    if not unique_news:
        logger.info("[파이프라인] 새로운 뉴스 없음. 종료.")
        return

    # 3. 중요도 채점
    scored_news = await score_importance(unique_news)

    # 4. 중요도 3 미만 필터링
    important_news = filter_by_importance(scored_news, min_importance=3)
    if not important_news:
        logger.info("[파이프라인] 중요도 3+ 뉴스 없음. 종료.")
        return

    # 5. 한국어 번역 + 요약
    translated_news = await translate_and_summarize(important_news)

    # 6. DB 저장
    saved_news = await save_to_db(translated_news)

    logger.info("=" * 50)
    logger.info(f"[파이프라인] 완료! {len(saved_news)}개 저장됨")
    logger.info("=" * 50)
