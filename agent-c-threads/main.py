"""
Agent C — Threads Auto Poster
중요도 3+ 뉴스 감지 → Threads 자동 포스팅
- twitter 타입: 인플루언서 트윗 직접 인용 형식
- news/analyst 타입: 뉴스 요약 형식
- 카테고리별 동적 해시태그
"""
import os
import logging
import asyncio
import httpx
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ── 로깅 ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent-c")

# ── 환경변수 ──────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "")
THREADS_API_BASE = "https://graph.threads.net/v1.0"
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))  # 5분

# ── Supabase 클라이언트 ───────────────────────────────────────────
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    logger.info("✅ Supabase 연결 완료")
else:
    logger.warning("⚠️  SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 미설정")

# ── 스케줄러 ──────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="UTC")

# ── 상태 추적 ─────────────────────────────────────────────────────
state = {
    "posts_sent": 0,
    "last_run": None,
    "last_post_id": None,
    "errors": 0,
    "running": False,
}

# ── 카테고리별 해시태그 ────────────────────────────────────────────
CATEGORY_HASHTAGS = {
    "crypto": "#비트코인 #BTC #크립토 #암호화폐 #Crypto",
    "macro": "#연준 #금리 #인플레이션 #매크로 #Fed #Macro",
    "crypto_macro": "#비트코인 #BTC #연준 #금리 #매크로 #Crypto #Macro",
    "macro_crypto": "#연준 #금리 #비트코인 #매크로 #Fed #Crypto",
    "stock": "#주식 #나스닥 #S&P500 #시장 #Stocks",
    "fed": "#연준 #FOMC #금리 #Fed #금융정책",
    "tech": "#기술주 #테크 #AI #Tech",
    "defi": "#DeFi #디파이 #탈중앙화 #크립토",
    "nft": "#NFT #크립토 #Web3",
    "regulation": "#규제 #SEC #크립토규제 #암호화폐",
}
DEFAULT_HASHTAGS = "#SIGNAL #시장분석 #투자 #크립토"


def get_hashtags(category: str, content_type: str) -> str:
    """카테고리 + 콘텐츠 타입에 맞는 해시태그 반환"""
    base = CATEGORY_HASHTAGS.get(category, DEFAULT_HASHTAGS)
    # 트위터 인용 포스트엔 #SIGNAL 추가
    tags = f"#SIGNAL {base}"
    return tags


# ── Threads API 헬퍼 ──────────────────────────────────────────────

async def create_threads_container(text: str) -> Optional[str]:
    """Threads 포스트 컨테이너 생성 → creation_id 반환"""
    url = f"{THREADS_API_BASE}/{THREADS_USER_ID}/threads"
    payload = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        creation_id = data.get("id")
        logger.info(f"컨테이너 생성 완료: {creation_id}")
        return creation_id


async def publish_threads_post(creation_id: str) -> Optional[str]:
    """Threads 포스트 발행 → post_id 반환"""
    url = f"{THREADS_API_BASE}/{THREADS_USER_ID}/threads_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        post_id = data.get("id")
        logger.info(f"포스트 발행 완료: {post_id}")
        return post_id


def format_twitter_post(news: dict) -> str:
    """트위터 인플루언서 트윗 → 직접 인용 형식 포스트"""
    # source 예: "Michael Saylor (@saylor)"
    source = news.get("source", "")
    title = news.get("title", "")          # tweet 원문 (최대 200자)
    summary = news.get("summary", "")      # tweet 원문 (최대 500자)
    source_url = news.get("source_url", "")
    category = news.get("category", "crypto")
    importance = news.get("importance", 3)

    # 트윗 본문: summary가 있으면 summary, 없으면 title 사용
    tweet_text = summary if summary else title
    # 500자 제한
    if len(tweet_text) > 450:
        tweet_text = tweet_text[:450] + "..."

    # 중요도 이모지
    importance_emoji = {5: "🚨", 4: "⚡", 3: "📌"}.get(importance, "📌")

    hashtags = get_hashtags(category, "twitter")

    # 원문 (title_original = 영어 원문)
    tweet_original = news.get("title_original", "")
    if len(tweet_original) > 300:
        tweet_original = tweet_original[:300] + "..."

    lines = [
        f"{importance_emoji} SIGNAL | 인플루언서 인사이트",
        f"",
        f"💬 {source}:",
    ]

    # 원문이 있고 한글 번역(tweet_text)과 다르면 병기
    if tweet_original and tweet_original != tweet_text:
        lines.append(f'"{tweet_original}"')
        lines.append(f"")
        lines.append(f"🇰🇷 {tweet_text}")
    else:
        lines.append(f'"{tweet_text}"')

    lines.append("")

    if source_url:
        lines.append(f"🔗 {source_url}")
        lines.append("")

    lines.append(hashtags)

    return "\n".join(lines)


def format_news_for_threads(news: dict) -> str:
    """뉴스/분석 아이템 → 뉴스 요약 형식 포스트"""
    title = news.get("title", "")
    summary = news.get("summary", "")
    source = news.get("source", "")
    source_url = news.get("source_url", "")
    category = news.get("category", "")
    importance = news.get("importance", 3)

    # 카테고리별 이모지
    category_emoji = {
        "crypto": "🪙",
        "macro": "📊",
        "stock": "📈",
        "fed": "🏦",
        "tech": "💻",
        "defi": "⛓️",
        "regulation": "⚖️",
    }.get(category, "📰")

    # 중요도 이모지
    importance_emoji = {5: "🚨", 4: "⚡", 3: "📌"}.get(importance, "📌")

    hashtags = get_hashtags(category, "news")

    lines = [
        f"{importance_emoji} SIGNAL | 중요도 {importance}/5",
        f"",
        f"{category_emoji} {title}",
        f"",
    ]

    if summary:
        trimmed_summary = summary[:200] + ("..." if len(summary) > 200 else "")
        lines.append(trimmed_summary)
        lines.append("")

    if source:
        lines.append(f"출처: {source}")

    if source_url:
        lines.append(source_url)

    lines.append("")
    lines.append(hashtags)

    return "\n".join(lines)


THREADS_MAX_LENGTH = 500  # Threads API 글자수 제한

# ── 토큰 자동 갱신 관련 ───────────────────────────────────────────
THREADS_TOKEN_REFRESH_THRESHOLD_DAYS = 15  # 만료 N일 전부터 갱신


async def get_token_expiry(token: str) -> int:
    """Threads API 디버그 엔드포인트로 만료시간(Unix timestamp) 조회"""
    url = "https://graph.threads.net/debug_token"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(url, params={"input_token": token, "access_token": token})
            data = resp.json()
            return data.get("data", {}).get("expires_at", 0)
        except Exception as e:
            logger.error(f"토큰 만료시간 조회 실패: {e}")
            return 0


async def refresh_threads_token(current_token: str) -> tuple:
    """Threads 장기 토큰 갱신 → (새_토큰, 만료_timestamp) 반환. 실패시 ("", 0)"""
    import time as _time
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                "https://graph.threads.net/refresh_access_token",
                params={"grant_type": "th_refresh_token", "access_token": current_token},
            )
            resp.raise_for_status()
            data = resp.json()
            new_token = data.get("access_token", "")
            expires_in = data.get("expires_in", 0)
            expiry_ts = int(_time.time()) + expires_in
            logger.info(
                f"✅ 토큰 갱신 성공! 새 만료일: "
                f"{datetime.fromtimestamp(expiry_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            )
            return new_token, expiry_ts
        except httpx.HTTPStatusError as e:
            logger.error(f"토큰 갱신 실패 (HTTP {e.response.status_code}): {e.response.text}")
            return "", 0
        except Exception as e:
            logger.error(f"토큰 갱신 오류: {e}")
            return "", 0


async def save_token_to_supabase(token: str, expires_at: int) -> bool:
    """갱신된 토큰을 Supabase app_settings 테이블에 저장 (upsert)"""
    if not supabase:
        return False
    try:
        expiry_iso = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
        result = supabase.table("app_settings").upsert({
            "key": "threads_access_token",
            "value": token,
            "expires_at": expiry_iso,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        if result.data:
            logger.info(f"✅ 토큰 Supabase 저장 완료 (만료: {expiry_iso})")
            return True
        logger.error("⚠️ Supabase 토큰 저장 실패 (data 없음)")
        return False
    except Exception as e:
        logger.error(f"Supabase 토큰 저장 오류: {e}")
        return False


async def load_token_from_supabase() -> tuple:
    """Supabase app_settings에서 저장된 토큰 로드 → (토큰, 만료_timestamp)"""
    if not supabase:
        return "", 0
    try:
        result = (
            supabase.table("app_settings")
            .select("value, expires_at")
            .eq("key", "threads_access_token")
            .execute()
        )
        if result.data:
            row = result.data[0]
            token = row.get("value", "")
            expires_at_str = row.get("expires_at", "")
            if expires_at_str:
                dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                return token, int(dt.timestamp())
        return "", 0
    except Exception as e:
        logger.error(f"Supabase 토큰 로드 오류: {e}")
        return "", 0


async def auto_refresh_token_job():
    """
    매일 실행되는 자동 갱신 Job
    - 만료 15일 전이면 자동 갱신
    - 갱신된 토큰을 메모리 + Supabase에 저장
    """
    global THREADS_ACCESS_TOKEN
    import time as _time

    logger.info("🔄 [토큰 점검] 만료 상태 확인 중...")

    # Supabase 우선, 없으면 환경변수 사용
    db_token, db_expires_ts = await load_token_from_supabase()
    if db_token:
        current_token, expires_ts = db_token, db_expires_ts
        logger.info("Supabase에서 토큰 로드됨")
    else:
        current_token = THREADS_ACCESS_TOKEN
        expires_ts = await get_token_expiry(current_token)
        logger.info("환경변수 토큰 사용 — 만료일 API 조회")

    if not current_token:
        logger.error("❌ 사용 가능한 토큰 없음 — 수동 발급 필요")
        return

    now_ts = int(_time.time())
    days_left = (expires_ts - now_ts) / 86400 if expires_ts else 0
    logger.info(f"토큰 만료까지: {days_left:.1f}일")

    if days_left <= THREADS_TOKEN_REFRESH_THRESHOLD_DAYS:
        logger.info(f"⚡ 만료 {days_left:.1f}일 전 → 자동 갱신 시작")
        new_token, new_expiry = await refresh_threads_token(current_token)
        if new_token:
            THREADS_ACCESS_TOKEN = new_token
            await save_token_to_supabase(new_token, new_expiry)
            new_days = (new_expiry - now_ts) / 86400
            logger.info(f"✅ 자동 갱신 완료! 새 만료까지: {new_days:.0f}일")
        else:
            logger.error("❌ 자동 갱신 실패! 수동 갱신 필요")
    else:
        logger.info(f"✅ 토큰 양호 ({days_left:.0f}일 남음)")


async def load_token_on_startup():
    """
    앱 시작시 Supabase에서 최신 토큰 로드
    (환경변수보다 Supabase 우선 — 자동 갱신된 토큰 반영)
    """
    global THREADS_ACCESS_TOKEN
    import time as _time

    db_token, db_expires_ts = await load_token_from_supabase()
    if db_token:
        now_ts = int(_time.time())
        days_left = (db_expires_ts - now_ts) / 86400 if db_expires_ts else -1
        if days_left > 0:
            THREADS_ACCESS_TOKEN = db_token
            logger.info(f"✅ Supabase 토큰 로드 완료 (만료까지 {days_left:.0f}일)")
        else:
            logger.warning(f"⚠️ Supabase 토큰 만료됨 ({abs(days_left):.0f}일 전) — 환경변수 사용")
    else:
        logger.info("ℹ️ Supabase 토큰 없음 → 환경변수 THREADS_ACCESS_TOKEN 사용")



def build_post_text(news: dict) -> str:
    """콘텐츠 타입에 따라 포맷 선택 + 500자 제한"""
    content_type = news.get("content_type", "news")
    if content_type in ("twitter", "influencer"):
        text = format_twitter_post(news)
    else:
        text = format_news_for_threads(news)

    # Threads API 500자 제한 초과 시 잘라내기
    if len(text) > THREADS_MAX_LENGTH:
        # 해시태그 라인 보존하며 본문만 줄이기
        lines = text.split("\n")
        hashtag_line = lines[-1] if lines[-1].startswith("#") else ""
        truncated = text[:THREADS_MAX_LENGTH - len(hashtag_line) - 5]
        # 마지막 완전한 줄 단위로 자르기
        last_newline = truncated.rfind("\n")
        if last_newline > 0:
            truncated = truncated[:last_newline]
        text = truncated + "\n\n" + hashtag_line if hashtag_line else truncated + "..."
        logger.warning(f"포스트 길이 초과({len(text)}자→{THREADS_MAX_LENGTH}자 제한) 잘라냄")

    return text


async def post_news_to_threads(news: dict) -> Optional[str]:
    """뉴스 1건을 Threads에 포스팅, post_id 반환"""
    text = build_post_text(news)

    try:
        creation_id = await create_threads_container(text)
        if not creation_id:
            raise ValueError("creation_id 없음")

        # Threads API 권장: 컨테이너 생성 후 잠깐 대기
        await asyncio.sleep(2)

        post_id = await publish_threads_post(creation_id)
        return post_id

    except httpx.HTTPStatusError as e:
        logger.error(f"Threads API HTTP 오류: {e.response.status_code} — {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Threads 포스팅 오류: {e}")
        return None


# ── 메인 폴링 로직 ────────────────────────────────────────────────

async def poll_and_post():
    """
    news 테이블에서 importance>=3 & posted_to_threads=false 항목을 찾아
    Threads에 포스팅하고 posted_to_threads=true로 업데이트
    - twitter/influencer 타입: 직접 인용 형식
    - news/analyst 타입: 뉴스 요약 형식
    """
    if not supabase:
        logger.warning("Supabase 미연결 — 폴링 건너뜀")
        return

    if not THREADS_ACCESS_TOKEN or not THREADS_USER_ID:
        logger.warning("Threads 자격증명 미설정 — 폴링 건너뜀")
        return

    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["running"] = True

    try:
        # importance>=3 & posted_to_threads=false 뉴스 조회 (최대 5건/회)
        result = (
            supabase.table("news")
            .select("id, title, title_original, summary, source, source_url, category, importance, content_type")
            .gte("importance", 3)
            .eq("posted_to_threads", False)
            .order("published_at", desc=False)
            .limit(5)
            .execute()
        )

        items = result.data or []
        logger.info(f"포스팅 대기 뉴스: {len(items)}건")

        for news in items:
            news_id = news["id"]
            content_type = news.get("content_type", "news")
            logger.info(f"포스팅 시작: [{news_id}][{content_type}] {news.get('title', '')[:50]}")

            post_id = await post_news_to_threads(news)

            if post_id:
                # posted_to_threads = true 업데이트 (실패 시 중복 포스팅 방지)
                update_result = supabase.table("news").update(
                    {"posted_to_threads": True}
                ).eq("id", news_id).execute()

                if not update_result.data:
                    logger.error(f"⚠️  DB 업데이트 실패: news_id={news_id} — 중복 포스팅 위험")
                    state["errors"] += 1
                else:
                    state["posts_sent"] += 1
                    state["last_post_id"] = post_id
                    logger.info(f"✅ 포스팅 완료: news_id={news_id}, post_id={post_id}")

                # 연속 포스팅 간 딜레이 (rate limit 방지)
                await asyncio.sleep(3)
            else:
                state["errors"] += 1
                logger.error(f"❌ 포스팅 실패: news_id={news_id}")

    except Exception as e:
        state["errors"] += 1
        logger.error(f"폴링 오류: {e}", exc_info=True)
    finally:
        state["running"] = False


# ── FastAPI 앱 ────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Agent C 시작 — Threads 자동 포스터")

    # 시작시 Supabase에서 최신 토큰 로드 (자동 갱신된 토큰 반영)
    await load_token_on_startup()

    if THREADS_ACCESS_TOKEN and THREADS_USER_ID and supabase:
        scheduler.add_job(
            poll_and_post,
            trigger=IntervalTrigger(seconds=POLL_INTERVAL_SECONDS),
            id="poll_and_post",
            replace_existing=True,
        )
        # 매일 09:00 UTC 토큰 만료 점검 + 자동 갱신
        scheduler.add_job(
            auto_refresh_token_job,
            trigger="cron",
            hour=9,
            minute=0,
            id="token_refresh",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(f"⏰ 스케줄러 시작 — 포스팅: {POLL_INTERVAL_SECONDS}초 간격, 토큰 점검: 매일 09:00 UTC")

        # 시작 직후 즉시 실행
        asyncio.create_task(poll_and_post())
        asyncio.create_task(auto_refresh_token_job())  # 시작시 즉시 점검
    else:
        logger.warning("⚠️  환경변수 미설정으로 스케줄러 비활성화")

    yield

    scheduler.shutdown(wait=False)
    logger.info("Agent C 종료")


app = FastAPI(
    title="SIGNAL Agent C — Threads Auto Poster",
    description="중요도 3+ 뉴스 → Threads 자동 포스팅 (트위터 인용 + 뉴스 요약)",
    version="2.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agent": "C",
        "version": "2.2.0",
        "scheduler": scheduler.running if scheduler else False,
        "supabase": supabase is not None,
        "threads_configured": bool(THREADS_ACCESS_TOKEN and THREADS_USER_ID),
    }


@app.get("/status")
async def status():
    return {
        "posts_sent": state["posts_sent"],
        "errors": state["errors"],
        "last_run": state["last_run"],
        "last_post_id": state["last_post_id"],
        "running": state["running"],
        "poll_interval_seconds": POLL_INTERVAL_SECONDS,
    }


@app.post("/post")
async def manual_post(background_tasks: BackgroundTasks):
    """수동 즉시 포스팅 트리거"""
    background_tasks.add_task(poll_and_post)
    return {"status": "triggered", "message": "포스팅 작업이 백그라운드에서 시작되었습니다"}


@app.post("/test-post")
async def test_post():
    """Threads API 연결 테스트 포스트"""
    if not THREADS_ACCESS_TOKEN or not THREADS_USER_ID:
        return {"error": "THREADS_ACCESS_TOKEN / THREADS_USER_ID 미설정"}

    test_news = {
        "id": "test",
        "title": "SIGNAL Agent C 작동 확인 테스트",
        "summary": "AI 기반 투자 신호 시스템 Agent C가 정상 작동하고 있습니다. 중요도 3+ 뉴스를 자동으로 Threads에 포스팅합니다.",
        "source": "SIGNAL",
        "source_url": "",
        "category": "tech",
        "importance": 3,
        "content_type": "news",
    }

    post_id = await post_news_to_threads(test_news)
    if post_id:
        return {"status": "success", "post_id": post_id, "message": "테스트 포스트 발행 완료"}
    else:
        return {"status": "error", "message": "테스트 포스트 발행 실패"}




@app.get("/token-status")
async def token_status():
    """Threads 토큰 만료 상태 조회"""
    import time as _time
    db_token, db_expires_ts = await load_token_from_supabase()
    current_token = db_token or THREADS_ACCESS_TOKEN
    expires_ts = db_expires_ts if db_token else await get_token_expiry(current_token)

    now_ts = int(_time.time())
    days_left = (expires_ts - now_ts) / 86400 if expires_ts else None
    source = "supabase" if db_token else "env_var"

    return {
        "token_source": source,
        "expires_at": datetime.fromtimestamp(expires_ts, tz=timezone.utc).isoformat() if expires_ts else None,
        "days_until_expiry": round(days_left, 1) if days_left is not None else None,
        "needs_refresh": days_left is not None and days_left <= THREADS_TOKEN_REFRESH_THRESHOLD_DAYS,
        "status": "ok" if (days_left and days_left > 0) else "expired",
    }


@app.post("/refresh-token")
async def manual_token_refresh():
    """수동 토큰 갱신 트리거 (긴급 상황용)"""
    await auto_refresh_token_job()
    db_token, db_expires_ts = await load_token_from_supabase()
    import time as _time
    now_ts = int(_time.time())
    days_left = (db_expires_ts - now_ts) / 86400 if db_expires_ts else 0
    return {
        "status": "refreshed" if db_token else "failed",
        "days_until_expiry": round(days_left, 1),
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
