"""
Agent C — Threads Auto Poster (Stub)
중요도 5 뉴스 감지 → Threads 자동 포스팅 (개발 예정)
"""
import os
import logging
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-c")

app = FastAPI(
    title="SIGNAL Agent C — Threads Poster",
    description="중요도 5 뉴스 → Threads 자동 포스팅",
    version="0.1.0-stub",
)


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "C", "mode": "stub"}


@app.on_event("startup")
async def startup():
    logger.info("Agent C 시작 (stub mode — Threads API 연동 개발 예정)")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
