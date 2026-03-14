"""
db.py — Supabase 데이터베이스 연결 모듈

쉽게 말하면: 우리 앱의 데이터가 저장되는 Supabase(클라우드 DB)에 접속하는 파일.
다른 파일에서 DB에 뭘 저장하거나 읽을 때 이 파일을 불러서 쓴다.

사용법:
    from db import supabase
    result = supabase.table("whale_alerts").select("*").execute()
"""

import os
from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

# 테스트 환경에서는 실제 Supabase 연결을 하지 않음
# TESTING 환경변수가 설정되어 있으면 None으로 두고, 테스트에서 mock 처리
_is_testing = os.getenv("TESTING", "false").lower() == "true"

if _is_testing:
    supabase = None  # 테스트에서 mock으로 대체됨
    print("[DB] 테스트 모드 — Supabase 연결 건너뜀")
else:
    from supabase import create_client, Client

    # Supabase 클라이언트 생성
    # service_role_key를 쓰면 RLS(보안 규칙)를 우회해서 모든 데이터에 접근 가능
    # → 서버(에이전트)에서만 사용! 앱(프론트)에서는 절대 이 키를 쓰면 안 됨
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    print("[DB] Supabase 연결 준비 완료")
