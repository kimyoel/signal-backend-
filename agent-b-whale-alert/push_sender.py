"""
push_sender.py — Expo 푸시 알림 발송 모듈

쉽게 말하면: 새 고래 거래가 감지되면, 앱 사용자들한테 "🐋 BTC 대형 이동!" 
같은 알림을 보내는 파일.

전체 흐름:
1. whale_monitor가 새 거래를 감지
2. DB에서 알림 받을 사용자 목록 조회 (구독 등급별 필터링)
3. 알림 메시지 만들기
4. Expo Push API로 배치 발송
5. 발송 완료 → whale_alerts.push_sent = true 업데이트
"""

import traceback
import httpx

from config import (
    EXPO_ACCESS_TOKEN,
    EXPO_PUSH_URL,
    EXPO_PUSH_BATCH_SIZE,
    FREE_USER_MIN_USD,
    PAID_USER_MIN_USD,
)
from db import supabase


def format_usd(amount_usd: float) -> str:
    """
    큰 금액을 읽기 쉽게 변환하는 함수.

    예시:
    - 112,000,000 → "$112.0M"
    - 2,300,000,000 → "$2.3B"
    - 500,000 → "$500.0K"
    """
    if amount_usd >= 1_000_000_000:
        return f"${amount_usd / 1_000_000_000:.1f}B"
    elif amount_usd >= 1_000_000:
        return f"${amount_usd / 1_000_000:.1f}M"
    else:
        return f"${amount_usd / 1_000:.1f}K"


def format_whale_push(whale: dict) -> dict:
    """
    고래 거래 데이터를 알림 메시지 형식으로 변환하는 함수.

    입력: whale_monitor에서 받은 거래 딕셔너리
    출력: Expo Push 형식의 title/body/data

    예시 결과:
    {
        "title": "🐋 BTC 대형 이동 감지",
        "body": "1,240 BTC ($112.0M)\nBinance → 미확인 지갑",
        "data": { "type": "whale_alert", "whale_id": "uuid", "screen": "whale_detail" }
    }
    """
    symbol = whale.get("symbol", "???").upper()
    amount = whale.get("amount", 0)
    amount_usd = whale.get("amount_usd", 0)
    from_label = whale.get("from_label", "미확인")
    to_label = whale.get("to_label", "미확인")

    # "unknown"을 한국어로 변환
    if from_label == "unknown":
        from_label = "미확인 지갑"
    if to_label == "unknown":
        to_label = "미확인 지갑"

    return {
        "title": f"🐋 {symbol} 대형 이동 감지",
        "body": f"{amount:,.0f} {symbol} ({format_usd(amount_usd)})\n{from_label} → {to_label}",
        "data": {
            "type": "whale_alert",
            "whale_id": str(whale.get("id", "")),
            "screen": "whale_detail",  # 앱에서 이 화면으로 자동 이동
        },
    }


def get_push_recipients(amount_usd: float) -> list[dict]:
    """
    푸시 알림을 받을 사용자 목록을 조회하는 함수.

    구독 등급별 필터링:
    - FREE 사용자: $500만 이상 거래만 알림 (과도한 알림 방지)
    - BASIC/PRO 사용자: $100만 이상 거래부터 알림

    개선: 사용자 + 구독을 2번의 DB 호출로 처리 (기존 N+1 문제 해결)

    반환값: [{"expo_push_token": "ExponentPushToken[xxx]", "plan": "free"}, ...]
    """
    try:
        # 1단계: 푸시 가능한 사용자 조회 (DB 호출 1회)
        # - expo_push_token이 있고 (앱에서 알림 허용한 사용자)
        # - push_enabled = true (알림 끄지 않은 사용자)
        # - notify_whale_min_usd <= 이번 거래 금액 (개인 설정 기준 충족)
        users_result = (
            supabase.table("users")
            .select("id, expo_push_token, notify_whale_min_usd")
            .not_.is_("expo_push_token", "null")
            .eq("push_enabled", True)
            .lte("notify_whale_min_usd", amount_usd)
            .execute()
        )

        if not users_result.data:
            print("[푸시] 알림 받을 사용자 없음")
            return []

        user_ids = [user["id"] for user in users_result.data]

        # 2단계: 해당 사용자들의 활성 구독을 한 번에 조회 (DB 호출 1회)
        # → 기존: 사용자마다 1번씩 = N번 호출 (느림)
        # → 개선: user_id IN (...) 으로 1번에 전부 가져옴 (빠름)
        subs_result = (
            supabase.table("subscriptions")
            .select("user_id, plan")
            .in_("user_id", user_ids)
            .eq("status", "active")
            .order("expires_at", desc=True)
            .execute()
        )

        # 사용자별 최신 구독 플랜 매핑 (같은 user_id가 여러 개면 첫 번째 = 최신)
        user_plan_map = {}
        for sub in (subs_result.data or []):
            uid = sub["user_id"]
            if uid not in user_plan_map:  # 첫 번째(최신)만 사용
                user_plan_map[uid] = sub["plan"]

        # 3단계: 등급별 금액 기준 필터링
        recipients = []
        for user in users_result.data:
            user_id = user["id"]

            # 구독이 없으면 FREE로 간주
            plan = user_plan_map.get(user_id, "free")

            # 등급별 금액 기준 체크
            if plan == "free" and amount_usd < FREE_USER_MIN_USD:
                # FREE 사용자인데 $500만 미만 → 알림 안 보냄
                continue

            if plan in ("basic", "pro") and amount_usd < PAID_USER_MIN_USD:
                # 유료 사용자인데 $100만 미만 → 알림 안 보냄
                continue

            recipients.append({
                "expo_push_token": user["expo_push_token"],
                "plan": plan,
            })

        print(f"[푸시] 알림 대상: {len(recipients)}명 (전체 {len(users_result.data)}명 중)")
        return recipients

    except Exception as e:
        print(f"[푸시] ⚠️ 사용자 조회 실패: {e}")
        traceback.print_exc()
        return []


def send_push_batch(messages: list[dict]) -> bool:
    """
    Expo Push API로 알림을 배치 발송하는 함수.
    최대 100개씩 묶어서 보낸다 (Expo 제한).

    입력: [{"to": "ExponentPushToken[xxx]", "title": "...", "body": "...", "data": {...}}, ...]
    반환값: 성공 여부 (True/False)
    """
    if not messages:
        return True

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Expo 토큰이 있으면 인증 헤더 추가
    if EXPO_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {EXPO_ACCESS_TOKEN}"

    success = True

    # 100개씩 묶어서 보내기 (Expo 제한)
    for i in range(0, len(messages), EXPO_PUSH_BATCH_SIZE):
        chunk = messages[i : i + EXPO_PUSH_BATCH_SIZE]
        chunk_num = (i // EXPO_PUSH_BATCH_SIZE) + 1

        try:
            response = httpx.post(
                EXPO_PUSH_URL,
                json=chunk,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()
            print(f"[푸시] 배치 {chunk_num}: {len(chunk)}건 발송 완료")

            # 실패한 토큰 확인 (Phase 2에서 자동 정리 구현 예정)
            if "data" in result:
                for idx, ticket in enumerate(result["data"]):
                    if ticket.get("status") == "error":
                        print(
                            f"[푸시] ⚠️ 발송 실패: {ticket.get('message', '알 수 없는 오류')}"
                        )

        except Exception as e:
            print(f"[푸시] ⚠️ 배치 {chunk_num} 발송 실패: {e}")
            success = False

    return success


def mark_push_sent(whale_ids: list[str]):
    """
    푸시 발송이 완료된 고래 알림의 상태를 업데이트하는 함수.
    whale_alerts 테이블에서 push_sent = true로 변경.
    """
    for whale_id in whale_ids:
        try:
            supabase.table("whale_alerts").update(
                {"push_sent": True}
            ).eq("id", whale_id).execute()
        except Exception as e:
            print(f"[푸시] ⚠️ push_sent 업데이트 실패 ({whale_id}): {e}")


def send_whale_alerts(new_whales: list[dict]):
    """
    새 고래 거래에 대해 알림을 발송하는 메인 함수.
    whale_monitor.run_whale_check() 결과를 받아서 처리한다.

    전체 흐름:
    1. 각 거래별로 알림 메시지 생성
    2. 대상 사용자 조회
    3. 배치 발송
    4. push_sent 상태 업데이트
    """
    if not new_whales:
        print("[푸시] 발송할 알림 없음")
        return

    print(f"[푸시] 📤 {len(new_whales)}건의 고래 알림 발송 시작")

    for whale in new_whales:
        amount_usd = whale.get("amount_usd", 0)
        whale_id = whale.get("id", "")

        # 1. 알림 메시지 만들기
        push_content = format_whale_push(whale)

        # 2. 이 금액 기준으로 알림 받을 사용자 조회
        recipients = get_push_recipients(amount_usd)

        if not recipients:
            print(f"[푸시] {whale.get('symbol', '?')} ${amount_usd:,.0f} → 대상 사용자 없음, 건너뜀")
            # 대상 없어도 push_sent는 true로 (다시 시도 안 하게)
            if whale_id:
                mark_push_sent([whale_id])
            continue

        # 3. 각 사용자에게 보낼 메시지 리스트 생성
        messages = []
        for recipient in recipients:
            messages.append({
                "to": recipient["expo_push_token"],
                "title": push_content["title"],
                "body": push_content["body"],
                "data": push_content["data"],
                "sound": "default",  # 알림 소리
                "priority": "high",  # 높은 우선순위
            })

        # 4. 배치 발송
        send_push_batch(messages)

        # 5. 발송 완료 표시
        if whale_id:
            mark_push_sent([whale_id])

        print(
            f"[푸시] ✅ {whale.get('symbol', '?')} "
            f"{format_usd(amount_usd)} → {len(recipients)}명 발송 완료"
        )

    print(f"[푸시] 📤 전체 발송 완료")
