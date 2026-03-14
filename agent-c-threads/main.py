"""
Agent C — Threads Auto Poster
중요도 5 뉴스 감지 → Threads 자동 포스팅
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


def format_news_for_threads(news: dict) -> str:
    """뉴스 아이템을 Threads 포스트 텍스트로 변환"""
    title = news.get("title", "")
    summary = news.get("summary", "")
    source = news.get("source", "")
    source_url = news.get("source_url", "")
    category = news.get("category", "")
    importance = news.get("importance", 5)

    # 카테고리별 이모지
    category_emoji = {
        "crypto": "🪙",
        "macro": "📊",
        "stock": "📈",
        "fed": "🏦",
        "tech": "💻",
    }.get(category, "📰")

    lines = [
        f"🚨 SIGNAL | 중요도 {importance}/5",
        f"",
        f"{category_emoji} {title}",
        f"",
    ]

    if summary:
        # 요약은 최대 200자
        trimmed_summary = summary[:200] + ("..." if len(summary) > 200 else "")
        lines.append(trimmed_summary)
        lines.append("")

    if source:
        lines.append(f"출처: {source}")

    if source_url:
        lines.append(source_url)

    lines.append("")
    lines.append("#SIGNAL #AI투자 #크립토 #시장분석")

    return "\n".join(lines)


async def post_news_to_threads(news: dict) -> Optional[str]:
    """뉴스 1건을 Threads에 포스팅, post_id 반환"""
    text = format_news_for_threads(news)

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
    news 테이블에서 importance>=4 & posted_to_threads=false 항목을 찾아
    Threads에 포스팅하고 posted_to_threads=true로 업데이트
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
        # importance>=4 & posted_to_threads=false 뉴스 조회 (최대 5건/회)
        # news: 4점+, twitter/analyst: 3점+ (content_type별 threshold)
        result = (
            supabase.table("news")
            .select("id, title, summary, source, source_url, category, importance, content_type")
            .gte("importance", 4)
            .eq("posted_to_threads", False)
            .order("published_at", desc=False)
            .limit(5)
            .execute()
        )

        items = result.data or []
        logger.info(f"포스팅 대기 뉴스: {len(items)}건")

        for news in items:
            news_id = news["id"]
            logger.info(f"포스팅 시작: [{news_id}] {news.get('title', '')[:50]}")

            post_id = await post_news_to_threads(news)

            if post_id:
                # posted_to_threads = true 업데이트
                supabase.table("news").update(
                    {"posted_to_threads": True}
                ).eq("id", news_id).execute()

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

    if THREADS_ACCESS_TOKEN and THREADS_USER_ID and supabase:
        scheduler.add_job(
            poll_and_post,
            trigger=IntervalTrigger(seconds=POLL_INTERVAL_SECONDS),
            id="poll_and_post",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(f"⏰ 스케줄러 시작 — {POLL_INTERVAL_SECONDS}초 간격")

        # 시작 직후 1회 즉시 실행
        asyncio.create_task(poll_and_post())
    else:
        logger.warning("⚠️  환경변수 미설정으로 스케줄러 비활성화")

    yield

    scheduler.shutdown(wait=False)
    logger.info("Agent C 종료")


app = FastAPI(
    title="SIGNAL Agent C — Threads Auto Poster",
    description="중요도 5 뉴스 → Threads 자동 포스팅",
    version="1.0.0",
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
        "version": "1.0.0",
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
        "summary": "AI 기반 투자 신호 시스템 Agent C가 정상 작동하고 있습니다. 중요도 5 뉴스를 자동으로 Threads에 포스팅합니다.",
        "source": "SIGNAL",
        "source_url": "",
        "category": "tech",
        "importance": 5,
    }

    post_id = await post_news_to_threads(test_news)
    if post_id:
        return {"status": "success", "post_id": post_id, "message": "테스트 포스트 발행 완료"}
    else:
        return {"status": "error", "message": "테스트 포스트 발행 실패"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
