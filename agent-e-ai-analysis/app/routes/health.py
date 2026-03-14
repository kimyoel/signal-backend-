# ============================================
# 헬스체크 라우터
# ============================================
# 서버가 살아있는지 확인하는 엔드포인트
# 비전공자 설명: "서버야 살아있어?" 하고 물으면 "응!" 이라고 대답하는 거
# ============================================

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    return {"status": "ok", "service": "SIGNAL Agent E — AI Analysis Engine"}


@router.get("/health")
async def health_check():
    return {"status": "healthy"}
