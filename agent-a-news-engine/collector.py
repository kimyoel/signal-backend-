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

# 인플루언서 X 계정 목록 (username: display_name, category, priority)
TWITTER_INFLUENCERS = [
    # 크립토 인플루언서
    {"username": "saylor",           "name": "Michael Saylor",    "category": "crypto",       "priority": 1},
    {"username": "APompliano",       "name": "Anthony Pompliano", "category": "crypto_macro", "priority": 2},
    {"username": "100trillionUSD",   "name": "PlanB",             "category": "crypto",       "priority": 2},
    {"username": "rektcapital",      "name": "Rekt Capital",      "category": "crypto",       "priority": 2},
    {"username": "nic__carter",      "name": "Nic Carter",        "category": "crypto",       "priority": 2},
    {"username": "scottmelker",      "name": "Scott Melker",      "category": "crypto",       "priority": 2},
    {"username": "milesdeutscher",   "name": "Miles Deutscher",   "category": "crypto",       "priority": 2},
    {"username": "woonomic",         "name": "Willy Woo",         "category": "crypto",       "priority": 2},
    {"username": "VitalikButerin",   "name": "Vitalik Buterin",   "category": "crypto",       "priority": 1},
    {"username": "brian_armstrong",  "name": "Brian Armstrong",   "category": "crypto",       "priority": 2},
    {"username": "el33th4xor",       "name": "Emin Gün Sirer",    "category": "crypto",       "priority": 2},
    # 매크로/주식 인플루언서
    {"username": "MacroAlf",         "name": "Alfonso Peccatiello", "category": "macro",      "priority": 1},
    {"username": "KobeissiLetter",   "name": "The Kobeissi Letter", "category": "macro",      "priority": 1},
    {"username": "charliebilello",   "name": "Charlie Bilello",   "category": "macro",        "priority": 2},
    {"username": "jsblokland",       "name": "Jeroen Blokland",   "category": "macro",        "priority": 2},
    {"username": "BillAckman",       "name": "Bill Ackman",       "category": "macro",        "priority": 2},
    {"username": "chamath",          "name": "Chamath Palihapitiya","category": "macro",       "priority": 2},
    {"username": "NickTimiraos",     "name": "Nick Timiraos",     "category": "macro",        "priority": 1},
    {"username": "LynAldenContact",  "name": "Lyn Alden",         "category": "macro_crypto", "priority": 1},
    {"username": "elerianm",         "name": "Mohamed El-Erian",  "category": "macro",        "priority": 2},
    {"username": "ritholtz",         "name": "Barry Ritholtz",    "category": "macro",        "priority": 3},
    {"username": "BobEUnlimited",    "name": "Bob Elliott",       "category": "macro",        "priority": 2},
    {"username": "GRDecter",         "name": "GR Decter",         "category": "macro",        "priority": 3},
    {"username": "LizAnnSonders",    "name": "Liz Ann Sonders",   "category": "macro",        "priority": 2},
    {"username": "PeterSchiff",      "name": "Peter Schiff",      "category": "macro_crypto", "priority": 3},
]


# ──────────────────────────────────────────
# 1단계: RSS 피드에서 뉴스 수집
# ──────────────────────────────────────────

async def fetch_rss_feed(source: dict) -> list[dict]:
    """하나의 RSS 피드에서 뉴스 항목들을 가져오는 함수

    Args:
        source: analyst_sources 테이블의 한 행
    """
    items = []
    try:
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, source["source_url"])

        for entry in feed.entries[:10]:  # 최대 10개
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", entry.get("description", ""))
            published = entry.get("published", "")

            if not title or not link:
                continue

            items.append({
                "title_original": title,
                "content_preview": summary[:500] if summary else title,
                "source": source["name"],
                "source_url": link,
                "category": source.get("category", "general"),
                "content_type": source.get("source_type", "rss"),
                "published_at": published or datetime.now(timezone.utc).isoformat(),
                "image_url": None,
            })

    except Exception as e:
        logger.error(f"[RSS] {source['name']} 수집 실패: {e}")

    logger.info(f"[RSS] {source['name']}: {len(items)}개 수집")
    return items


# ──────────────────────────────────────────
# 1-B단계: Twitter/X 인플루언서 트윗 수집
# ──────────────────────────────────────────

async def fetch_twitter_influencer(influencer: dict, api_key: str, count: int = 5) -> list[dict]:
    """twitterapi.io를 사용해 인플루언서 최신 트윗 수집

    Args:
        influencer: TWITTER_INFLUENCERS 목록의 항목
        api_key: twitterapi.io API 키
        count: 가져올 트윗 수
    """
    items = []
    username = influencer["username"]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.twitterapi.io/twitter/user/last_tweets",
                params={"userName": username, "count": count},
                headers={"X-API-Key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "success":
            logger.warning(f"[Twitter] @{username} API 오류: {data.get('msg', 'unknown')}")
            return items

        tweet_data = data.get("data", {})

        # 정지/접근불가 계정 처리
        if isinstance(tweet_data, dict) and tweet_data.get("unavailable"):
            reason = tweet_data.get("unavailableReason", "Unknown")
            logger.warning(f"[Twitter] @{username} 접근 불가: {reason}")
            return items

        tweets = tweet_data.get("tweets", [])

        for tweet in tweets:
            text = tweet.get("text", "")
            tweet_id = tweet.get("id", "")
            created_at = tweet.get("createdAt", "")

            # RT(리트윗) 제외 옵션 — 원글만 수집
            if text.startswith("RT @"):
                continue

            # 너무 짧은 트윗 제외 (링크만 있는 경우 등)
            if len(text.strip()) < 30:
                continue

            tweet_url = f"https://x.com/{username}/status/{tweet_id}"

            items.append({
                "title_original": text[:200],
                "content_preview": text[:500],
                "source": f"{influencer['name']} (@{username})",
                "source_url": tweet_url,
                "category": influencer["category"],
                "content_type": "twitter",
                "published_at": created_at or datetime.now(timezone.utc).isoformat(),
                "image_url": None,
                "author_priority": influencer["priority"],
            })

    except httpx.HTTPStatusError as e:
        logger.error(f"[Twitter] @{username} HTTP 오류: {e.response.status_code}")
    except Exception as e:
        logger.error(f"[Twitter] @{username} 수집 실패: {e}")

    if items:
        logger.info(f"[Twitter] @{username}: {len(items)}개 트윗 수집")
    return items


async def fetch_all_twitter(api_key: str) -> list[dict]:
    """전체 인플루언서 트윗 수집 (순차 실행 — rate limit 대응)"""
    all_tweets = []
    logger.info(f"[Twitter] 인플루언서 {len(TWITTER_INFLUENCERS)}명 수집 시작")

    for influencer in TWITTER_INFLUENCERS:
        tweets = await fetch_twitter_influencer(influencer, api_key, count=5)
        all_tweets.extend(tweets)
        await asyncio.sleep(6)  # twitterapi.io 무료 티어: 5초에 1요청

    logger.info(f"[Twitter] 총 {len(all_tweets)}개 트윗 수집 완료")
    return all_tweets


# ──────────────────────────────────────────
# 2단계: NewsAPI에서 뉴스 수집
# ──────────────────────────────────────────

async def fetch_newsapi() -> list[dict]:
    """NewsAPI를 사용해서 여러 키워드로 뉴스를 수집하는 함수"""
    items = []
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        logger.warning("[NewsAPI] NEWSAPI_KEY 없음, 건너뜀")
        return items

    async with httpx.AsyncClient(timeout=30.0) as client:
        for keyword in NEWSAPI_KEYWORDS[:5]:
            try:
                resp = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": keyword,
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": 5,
                        "apiKey": api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                for article in data.get("articles", []):
                    title = article.get("title", "")
                    url = article.get("url", "")
                    description = article.get("description", "")
                    published = article.get("publishedAt", "")
                    source_name = article.get("source", {}).get("name", "NewsAPI")
                    image_url = article.get("urlToImage")

                    if not title or not url:
                        continue

                    items.append({
                        "title_original": title,
                        "content_preview": description[:500] if description else title,
                        "source": source_name,
                        "source_url": url,
                        "category": "general",
                        "content_type": "news",
                        "published_at": published or datetime.now(timezone.utc).isoformat(),
                        "image_url": image_url,
                    })

            except Exception as e:
                logger.error(f"[NewsAPI] '{keyword}' 수집 실패: {e}")

    logger.info(f"[NewsAPI] 총 {len(items)}개 수집")
    return items


# ──────────────────────────────────────────
# 3단계: 중복 제거
# ──────────────────────────────────────────

async def remove_duplicates(news_items: list[dict]) -> list[dict]:
    """source_url 기준 중복 제거 (DB + 이번 배치 내부)"""
    supabase = get_supabase_client()
    unique = []
    seen_urls = set()

    for item in news_items:
        url = item.get("source_url", "")
        if not url or url in seen_urls:
            continue
        is_dup = await check_duplicate_url(supabase, url)
        if not is_dup:
            unique.append(item)
            seen_urls.add(url)

    logger.info(f"[중복제거] {len(news_items)}개 → {len(unique)}개")
    return unique


# ──────────────────────────────────────────
# 4단계: 중요도 채점 (Gemini Flash-Lite)
# ──────────────────────────────────────────

async def score_importance(news_items: list[dict]) -> list[dict]:
    """Gemini Flash-Lite로 중요도 1~5 채점"""
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        logger.warning("[채점] GOOGLE_AI_API_KEY 없음 → 기본값 3 적용")
        for item in news_items:
            item["importance"] = 3
        return news_items

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash-lite")

    for item in news_items:
        try:
            prompt = SCORING_PROMPT.format(
                title=item["title_original"],
                content_preview=item.get("content_preview", ""),
            )
            response = model.generate_content(prompt)
            text = response.text.strip()

            # 숫자 추출 (1~5)
            import re
            numbers = re.findall(r'\b[1-5]\b', text)
            score = int(numbers[0]) if numbers else 3
            item["importance"] = max(1, min(5, score))

        except Exception as e:
            logger.error(f"[채점] 오류: {e}")
            item["importance"] = 3

    return news_items


# ──────────────────────────────────────────
# 5단계: 중요도 필터링
# ──────────────────────────────────────────

def filter_by_importance(news_items: list[dict], min_importance: int = 3) -> list[dict]:
    """중요도 min_importance 이상만 통과"""
    filtered = [item for item in news_items if item.get("importance", 0) >= min_importance]
    logger.info(f"[필터] 중요도 {min_importance}+ : {len(filtered)}개 통과 / {len(news_items)}개 중")
    return filtered


# ──────────────────────────────────────────
# 6단계: 한국어 번역 + 요약 (Gemini Flash)
# ──────────────────────────────────────────

async def translate_and_summarize(news_items: list[dict]) -> list[dict]:
    """Gemini Flash로 한국어 번역 + 1~2문장 요약"""
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        logger.warning("[번역] GOOGLE_AI_API_KEY 없음 → 원문 유지")
        for item in news_items:
            item["title"] = item["title_original"]
            item["summary"] = item.get("content_preview", "")[:200]
        return news_items

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    for item in news_items:
        try:
            prompt = TRANSLATE_SUMMARIZE_PROMPT.format(
                title=item["title_original"],
                content=item.get("content_preview", ""),
            )
            response = model.generate_content(prompt)
            text = response.text.strip()

            # JSON 파싱 시도
            import re
            json_match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                item["title"] = result.get("title_ko", item["title_original"])
                item["summary"] = result.get("summary_ko", item.get("content_preview", "")[:200])
            else:
                item["title"] = item["title_original"]
                item["summary"] = text[:200]

        except Exception as e:
            logger.error(f"[번역] 오류: {e}")
            item["title"] = item["title_original"]
            item["summary"] = item.get("content_preview", "")[:200]

    return news_items


# ──────────────────────────────────────────
# 7단계: DB 저장
# ──────────────────────────────────────────

async def save_to_db(news_items: list[dict]) -> list[dict]:
    """news 테이블에 저장, 중요도 4+ 트위터 / 5 뉴스는 posted_to_threads=false"""
    supabase = get_supabase_client()
    records = []

    for item in news_items:
        content_type = item.get("content_type", "news")
        importance = item.get("importance", 3)

        # Threads 포스팅 대상 결정
        # - 뉴스/RSS: 중요도 5
        # - 트위터/애널리스트: 중요도 4+
        if content_type == "twitter":
            post_to_threads = importance >= 4
        elif content_type in ("analyst", "influencer"):
            post_to_threads = importance >= 3
        else:
            post_to_threads = importance >= 5

        records.append({
            "title": item.get("title", item.get("title_original", "")),
            "title_original": item.get("title_original", ""),
            "summary": item.get("summary", ""),
            "source": item.get("source", ""),
            "source_url": item.get("source_url", ""),
            "category": item.get("category", "general"),
            "importance": importance,
            "published_at": item.get("published_at"),
            "image_url": item.get("image_url"),
            "has_analysis": False,
            "posted_to_threads": not post_to_threads,  # False = 포스팅 대기
            "content_type": content_type,
        })

    saved = await save_news_batch(supabase, records)
    logger.info(f"[DB저장] {len(saved)}개 저장 완료")
    return saved


# ──────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────

async def run_collection_pipeline():
    """뉴스 + 트위터 수집 전체 파이프라인 (30분마다 실행)

    1. RSS + NewsAPI에서 뉴스 수집
    2. Twitter 인플루언서 트윗 수집
    3. 중복 제거
    4. 중요도 채점 (Gemini Flash-Lite)
    5. 중요도 3 미만 필터링
    6. 한국어 번역 + 요약 (Gemini Flash)
    7. DB 저장
    """
    logger.info("=" * 50)
    logger.info("[파이프라인] 뉴스 + 트위터 수집 시작")
    logger.info("=" * 50)

    # 1. RSS 소스에서 뉴스 수집
    rss_sources = await load_rss_sources()
    rss_tasks = [fetch_rss_feed(source) for source in rss_sources if source["source_type"] == "rss"]
    rss_results = await asyncio.gather(*rss_tasks, return_exceptions=True)

    all_news = []
    for result in rss_results:
        if isinstance(result, list):
            all_news.extend(result)

    # NewsAPI 뉴스 추가
    newsapi_news = await fetch_newsapi()
    all_news.extend(newsapi_news)

    logger.info(f"[수집] RSS+NewsAPI: {len(all_news)}개")

    # 2. Twitter 인플루언서 트윗 수집
    twitter_api_key = os.getenv("TWITTER_API_KEY")
    if twitter_api_key:
        twitter_news = await fetch_all_twitter(twitter_api_key)
        all_news.extend(twitter_news)
        logger.info(f"[수집] Twitter 포함 총: {len(all_news)}개")
    else:
        logger.warning("[Twitter] TWITTER_API_KEY 없음, Twitter 수집 건너뜀")

    if not all_news:
        logger.info("[파이프라인] 수집된 뉴스 없음. 종료.")
        return

    # 3. 중복 제거
    unique_news = await remove_duplicates(all_news)
    if not unique_news:
        logger.info("[파이프라인] 새로운 뉴스 없음. 종료.")
        return

    # 4. 중요도 채점
    scored_news = await score_importance(unique_news)

    # 5. 중요도 3 미만 필터링
    important_news = filter_by_importance(scored_news, min_importance=3)
    if not important_news:
        logger.info("[파이프라인] 중요도 3+ 없음. 종료.")
        return

    # 6. 한국어 번역 + 요약
    translated_news = await translate_and_summarize(important_news)

    # 7. DB 저장
    saved_news = await save_to_db(translated_news)

    logger.info("=" * 50)
    logger.info(f"[파이프라인] 완료! {len(saved_news)}개 저장됨")
    logger.info("=" * 50)
