# ─────────────────────────────────────────
# main.py — 에이전트 A 진입점
# FastAPI 서버 + APScheduler (30분마다 뉴스 수집)
# Railway에서 이 파일을 실행함: uvicorn main:app --host 0.0.0.0 --port 8000
# ─────────────────────────────────────────

import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from collector import run_collection_pipeline
from analyzer import run_analysis

# .env 파일에서 환경변수 로드
load_dotenv()

# ──────────────────────────────────────────
# 로깅 설정
# ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# ──────────────────────────────────────────
# FastAPI 앱 생성
# ──────────────────────────────────────────
app = FastAPI(
    title="SIGNAL 에이전트 A",
    description="뉴스 수집 + AI 3각 분석 엔진",
    version="1.0.0",
)

# CORS 설정 (앱에서 호출할 수 있게)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 앱 도메인만 허용하도록 변경
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────
# APScheduler 설정 (30분마다 뉴스 수집)
# ──────────────────────────────────────────
scheduler = AsyncIOScheduler()


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 스케줄러 등록"""
    # 30분마다 뉴스 수집 파이프라인 실행
    scheduler.add_job(
        run_collection_pipeline,
        "interval",
        minutes=30,
        id="news_collection",
        name="뉴스 수집 파이프라인 (30분)",
    )
    scheduler.start()
    logger.info("✅ APScheduler 시작 — 30분마다 뉴스 수집")

    # 서버 시작 시 즉시 1회 실행
    logger.info("🚀 서버 시작 — 첫 뉴스 수집 즉시 실행")
    asyncio.create_task(run_collection_pipeline())


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 스케줄러 정리"""
    scheduler.shutdown()
    logger.info("⛔ APScheduler 종료")


# ──────────────────────────────────────────
# API 엔드포인트
# ──────────────────────────────────────────

# 요청 Body 스키마
class AnalyzeRequest(BaseModel):
    news_id: str   # 분석할 뉴스 UUID
    user_id: str   # 요청한 사용자 UUID


@app.get("/")
async def root():
    """헬스 체크 — 서버가 살아있는지 확인용"""
    return {
        "service": "SIGNAL 에이전트 A",
        "status": "running",
        "version": "1.0.0",
    }


@app.post("/analyze")
async def analyze_news(request: AnalyzeRequest):
    """AI 3각 분석 요청 엔드포인트

    - 앱(에이전트 D)이 이 엔드포인트를 호출
    - news_id와 user_id를 받아서 분석 실행

    흐름:
    1. 캐시 확인 → 있으면 바로 반환
    2. 크레딧 확인 → 0이면 거절
    3. GPT + Gemini + Grok 병렬 호출
    4. Claude 검증
    5. DB 저장 + 크레딧 차감
    6. 결과 반환
    """
    result = await run_analysis(request.news_id, request.user_id)

    if not result["success"]:
        if result["error"] == "insufficient_credits":
            raise HTTPException(status_code=402, detail=result)
        elif result["error"] == "news_not_found":
            raise HTTPException(status_code=404, detail=result)
        else:
            raise HTTPException(status_code=500, detail=result)

    return result


@app.post("/collect")
async def trigger_collection():
    """수동으로 뉴스 수집 트리거 (디버그/관리용)

    - 30분 주기를 기다리지 않고 즉시 수집 실행
    - 관리자만 호출 (프로덕션에서는 인증 필요)
    """
    logger.info("📡 수동 수집 트리거됨")
    asyncio.create_task(run_collection_pipeline())
    return {"message": "뉴스 수집이 시작되었습니다. 백그라운드에서 실행 중..."}


@app.get("/status")
async def get_status():
    """스케줄러 상태 확인"""
    jobs = scheduler.get_jobs()
    return {
        "scheduler_running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in jobs
        ],
    }

@app.get("/debug-env")
async def debug_env():
    """환경변수 이름 목록 (값 제외)"""
    import os
    keys = [
        "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
        "GOOGLE_AI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY",
        "ANTHROPIC_API_KEY", "NEWSAPI_KEY", "TWITTER_API_KEY",
        "GEMINI_API_KEY", "GOOGLE_API_KEY"
    ]
    result = {}
    for k in keys:
        val = os.getenv(k)
        if val:
            result[k] = f"SET ({len(val)}chars)"
        else:
            result[k] = "NOT SET"
    return result


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
