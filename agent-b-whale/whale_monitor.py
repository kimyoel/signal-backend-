"""
whale_monitor.py — 고래 알림 감시 모듈

쉽게 말하면: 5분마다 Whale Alert API에 "큰 거래 있었어?" 하고 물어보고,
있으면 우리 DB에 저장하는 파일.

전체 흐름:
1. Whale Alert API 호출 → 최근 대형 거래 목록 받아옴
2. 이미 저장한 거래인지 확인 (tx_hash로 중복 체크)
3. 새 거래만 whale_alerts 테이블에 저장
4. 저장된 새 거래 목록을 반환 → push_sender.py가 알림 발송
"""

import time
import traceback
import httpx
from datetime import datetime, timezone

from config import (
    WHALE_ALERT_API_KEY,
    WHALE_ALERT_BASE_URL,
    WHALE_MIN_VALUE_USD,
    WHALE_TRACKED_SYMBOLS,
)
from db import supabase


# ──────────────────────────────────────────────
# 마지막으로 처리한 시간 (메모리에 보관)
# 서버가 재시작되면 초기화되므로, 처음엔 10분 전부터 조회
# Phase 2에서 DB에 저장하는 방식으로 개선 예정
# ──────────────────────────────────────────────
_last_cursor_timestamp: int = 0


def _get_start_timestamp() -> int:
    """
    API 조회 시작 시점을 결정하는 함수.
    - 이전에 조회한 적 있으면 → 그 시점부터
    - 처음이면 → 10분 전부터
    """
    global _last_cursor_timestamp

    if _last_cursor_timestamp > 0:
        return _last_cursor_timestamp

    # 처음 실행: 10분 전부터 조회 (너무 과거 데이터 방지)
    return int(time.time()) - 600


def fetch_whale_transactions() -> list[dict]:
    """
    Whale Alert API에서 대형 거래 목록을 가져오는 함수.

    반환값: 거래 딕셔너리 리스트
    [
        {
            "blockchain": "bitcoin",
            "symbol": "BTC",
            "amount": 1240.5,
            "amount_usd": 112000000,
            "from_address": "1A1zP...",
            "to_address": "3J98t...",
            "from_label": "Binance",
            "to_label": "unknown",
            "tx_hash": "abc123...",
            "whale_alert_id": "123456",
            "occurred_at": "2026-03-14T12:00:00+00:00"
        },
        ...
    ]
    """
    global _last_cursor_timestamp
    start_time = _get_start_timestamp()

    print(f"[고래감시] API 호출 시작 (시작점: {datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat()})")

    try:
        # Whale Alert API 호출
        response = httpx.get(
            WHALE_ALERT_BASE_URL,
            params={
                "api_key": WHALE_ALERT_API_KEY,
                "min_value": WHALE_MIN_VALUE_USD,
                "start": start_time,
            },
            timeout=30,  # 30초 타임아웃
        )
        response.raise_for_status()  # HTTP 에러 시 예외 발생
        data = response.json()

    except httpx.TimeoutException:
        print("[고래감시] ⚠️ API 요청 타임아웃 (30초 초과)")
        return []
    except httpx.HTTPStatusError as e:
        print(f"[고래감시] ⚠️ API HTTP 에러: {e.response.status_code}")
        return []
    except Exception as e:
        print(f"[고래감시] ⚠️ API 호출 실패: {e}")
        traceback.print_exc()
        return []

    # API 응답 확인
    if data.get("result") != "success":
        print(f"[고래감시] ⚠️ API 응답 실패: {data.get('message', '알 수 없는 오류')}")
        return []

    transactions = data.get("transactions", [])
    print(f"[고래감시] API에서 {len(transactions)}건의 거래 수신")

    # 거래 데이터를 우리 형식으로 변환
    parsed = []
    for tx in transactions:
        symbol = tx.get("symbol", "").upper()

        # 감시 대상 코인이 아니면 건너뛰기
        if symbol not in WHALE_TRACKED_SYMBOLS:
            continue

        parsed.append({
            "blockchain": tx.get("blockchain", "unknown"),
            "symbol": symbol,
            "amount": float(tx.get("amount", 0)),
            "amount_usd": float(tx.get("amount_usd", 0)),
            "from_address": tx.get("from", {}).get("address", "unknown"),
            "to_address": tx.get("to", {}).get("address", "unknown"),
            "from_label": tx.get("from", {}).get("owner", "unknown"),
            "to_label": tx.get("to", {}).get("owner", "unknown"),
            "tx_hash": tx.get("hash", ""),
            "whale_alert_id": str(tx.get("id", "")),
            "occurred_at": datetime.fromtimestamp(
                tx.get("timestamp", 0), tz=timezone.utc
            ).isoformat(),
        })

    # 다음 호출을 위해 마지막 타임스탬프 업데이트
    if transactions:
        latest_ts = max(tx.get("timestamp", 0) for tx in transactions)
        _last_cursor_timestamp = latest_ts + 1  # +1초: 같은 거래 다시 안 가져오게

    print(f"[고래감시] 감시 대상 코인 필터 후 {len(parsed)}건")
    return parsed


def filter_new_transactions(transactions: list[dict]) -> list[dict]:
    """
    이미 DB에 저장된 거래를 제외하고, 새 거래만 반환하는 함수.
    tx_hash를 기준으로 중복 체크한다.

    왜 중복 체크를 하나?
    → Whale Alert API가 같은 거래를 여러 번 반환할 수 있어서.
    """
    if not transactions:
        return []

    # DB에서 tx_hash 목록 조회
    tx_hashes = [tx["tx_hash"] for tx in transactions if tx["tx_hash"]]

    if not tx_hashes:
        return transactions

    try:
        # 이미 저장된 tx_hash 조회
        result = (
            supabase.table("whale_alerts")
            .select("tx_hash")
            .in_("tx_hash", tx_hashes)
            .execute()
        )
        existing_hashes = {row["tx_hash"] for row in result.data}
    except Exception as e:
        print(f"[고래감시] ⚠️ 중복 체크 실패 (전체 저장 시도): {e}")
        existing_hashes = set()

    # 새 거래만 필터
    new_transactions = [
        tx for tx in transactions if tx["tx_hash"] not in existing_hashes
    ]

    skipped = len(transactions) - len(new_transactions)
    if skipped > 0:
        print(f"[고래감시] 중복 {skipped}건 제외, 신규 {len(new_transactions)}건")

    return new_transactions


def save_to_database(transactions: list[dict]) -> list[dict]:
    """
    새 거래를 whale_alerts 테이블에 저장하는 함수.
    push_sent=false로 저장해서, 나중에 push_sender가 알림을 보낸다.

    반환값: 저장에 성공한 거래 리스트
    """
    if not transactions:
        return []

    saved = []

    for tx in transactions:
        try:
            # DB에 저장할 데이터 구성
            row = {
                "blockchain": tx["blockchain"],
                "symbol": tx["symbol"],
                "amount": tx["amount"],
                "amount_usd": tx["amount_usd"],
                "from_address": tx["from_address"],
                "to_address": tx["to_address"],
                "from_label": tx["from_label"],
                "to_label": tx["to_label"],
                "tx_hash": tx["tx_hash"],
                "whale_alert_id": tx["whale_alert_id"],
                "occurred_at": tx["occurred_at"],
                "push_sent": False,  # 아직 푸시 안 보냄
            }

            result = supabase.table("whale_alerts").insert(row).execute()

            if result.data:
                # 저장 성공 → ID 추가해서 반환 리스트에 넣기
                saved_row = result.data[0]
                tx["id"] = saved_row["id"]
                saved.append(tx)
                print(
                    f"[고래감시] ✅ 저장: {tx['symbol']} "
                    f"{tx['amount']:,.0f}개 (${tx['amount_usd']:,.0f})"
                )

        except Exception as e:
            # 하나 실패해도 나머지는 계속 저장 시도
            print(f"[고래감시] ⚠️ 저장 실패 ({tx['tx_hash'][:10]}...): {e}")
            continue

    print(f"[고래감시] 총 {len(saved)}건 신규 저장 완료")
    return saved


def run_whale_check() -> list[dict]:
    """
    고래 감시의 메인 실행 함수.
    main.py의 APScheduler가 5분마다 이 함수를 호출한다.

    전체 흐름: API 호출 → 중복 제거 → DB 저장 → 새 거래 반환

    반환값: 새로 저장된 거래 리스트 (push_sender에게 전달용)
    """
    print()
    print("=" * 50)
    print(f"[고래감시] 🐋 감시 시작: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 50)

    # 1단계: API에서 거래 가져오기
    transactions = fetch_whale_transactions()
    if not transactions:
        print("[고래감시] 새 거래 없음 — 다음 주기에 다시 확인")
        return []

    # 2단계: 중복 제거
    new_transactions = filter_new_transactions(transactions)
    if not new_transactions:
        print("[고래감시] 모두 이미 저장된 거래 — 건너뜀")
        return []

    # 3단계: DB에 저장
    saved = save_to_database(new_transactions)

    print(f"[고래감시] 🐋 감시 완료: 신규 {len(saved)}건 처리됨")
    return saved
