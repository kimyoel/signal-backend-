"""
whale_monitor.py — 고래 알림 감시 모듈 (Bitquery v2 API 사용)

쉽게 말하면: 5분마다 Bitquery GraphQL API에 "큰 거래 있었어?" 하고 물어보고,
있으면 우리 DB에 저장하는 파일.

Whale Alert(유료) → Bitquery(무료 Developer Plan) 로 교체
- 지원 체인: BTC, ETH, SOL, BSC 등 40개+
- 무료 한도: 1k points/월, 실시간 스트림 2개, 웹훅 지원
- API 문서: https://docs.bitquery.io

전체 흐름:
1. Bitquery GraphQL API 호출 → 최근 5분간 대형 거래 목록
2. 이미 저장한 거래인지 확인 (tx_hash로 중복 체크)
3. 새 거래만 whale_alerts 테이블에 저장
4. 저장된 새 거래 목록을 반환 → push_sender.py가 알림 발송
"""

import time
import traceback
import httpx
from datetime import datetime, timezone, timedelta

from config import (
    BITQUERY_API_KEY,
    BITQUERY_API_URL,
    WHALE_MIN_VALUE_USD,
    WHALE_TRACKED_SYMBOLS,
)
from db import supabase


# ──────────────────────────────────────────────
# 마지막으로 처리한 시간 (메모리에 보관)
# 서버가 재시작되면 초기화되므로, 처음엔 10분 전부터 조회
# ──────────────────────────────────────────────
_last_cursor_time: datetime | None = None


def _get_time_range() -> tuple[str, str]:
    """
    Bitquery API 조회 시간 범위를 결정하는 함수.
    - 이전에 조회한 적 있으면 → 그 시점부터 현재까지
    - 처음이면 → 10분 전부터 현재까지
    반환값: (since_iso, till_iso) — ISO8601 문자열
    """
    global _last_cursor_time
    now = datetime.now(timezone.utc)

    if _last_cursor_time is not None:
        since = _last_cursor_time
    else:
        since = now - timedelta(minutes=10)

    return since.strftime("%Y-%m-%dT%H:%M:%SZ"), now.strftime("%Y-%m-%dT%H:%M:%SZ")


# ──────────────────────────────────────────────
# 체인별 Bitquery 네트워크 이름 매핑
# ──────────────────────────────────────────────
SYMBOL_TO_NETWORK = {
    "BTC": "bitcoin",
    "ETH": "eth",
    "USDT": "eth",   # ERC-20 USDT
    "USDC": "eth",   # ERC-20 USDC
    "SOL": "solana",
}

# EVM 체인 (ETH, USDT, USDC) 은 한 번에 조회 가능
EVM_SYMBOLS = {"ETH", "USDT", "USDC"}


def _fetch_evm_whales(since: str, till: str) -> list[dict]:
    """
    Ethereum 체인의 대형 토큰 이동을 Bitquery로 조회.
    ETH, USDT, USDC 한 번에 가져옴.
    """
    min_usd = WHALE_MIN_VALUE_USD

    query = """
    query WhaleTransfersEVM($since: ISO8601DateTime, $till: ISO8601DateTime, $minUsd: Float) {
      EVM(network: eth) {
        Transfers(
          where: {
            Transfer: {AmountInUSD: {gt: $minUsd}}
            Block: {Time: {since: $since, till: $till}}
          }
          orderBy: {descending: Block_Time}
          limit: {count: 50}
        ) {
          Block {
            Time
            Number
          }
          Transaction {
            Hash
          }
          Transfer {
            Amount
            AmountInUSD
            Currency {
              Symbol
              Name
            }
            Sender
            Receiver
          }
        }
      }
    }
    """

    try:
        resp = httpx.post(
            BITQUERY_API_URL,
            headers={
                "Authorization": f"Bearer {BITQUERY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "variables": {
                    "since": since,
                    "till": till,
                    "minUsd": min_usd,
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.TimeoutException:
        print("[고래감시-EVM] ⚠️ API 타임아웃")
        return []
    except Exception as e:
        print(f"[고래감시-EVM] ⚠️ API 오류: {e}")
        return []

    if "errors" in data:
        print(f"[고래감시-EVM] ⚠️ GraphQL 에러: {data['errors'][0].get('message','')}")
        return []

    transfers = data.get("data", {}).get("EVM", {}).get("Transfers", [])
    results = []

    for t in transfers:
        symbol = t["Transfer"]["Currency"]["Symbol"].upper()
        if symbol not in EVM_SYMBOLS:
            continue
        if symbol not in WHALE_TRACKED_SYMBOLS:
            continue

        results.append({
            "blockchain": "ethereum",
            "symbol": symbol,
            "amount": float(t["Transfer"]["Amount"]),
            "amount_usd": float(t["Transfer"]["AmountInUSD"]),
            "from_address": t["Transfer"]["Sender"],
            "to_address": t["Transfer"]["Receiver"],
            "from_label": "unknown",
            "to_label": "unknown",
            "tx_hash": t["Transaction"]["Hash"],
            "whale_alert_id": t["Transaction"]["Hash"][:16],
            "occurred_at": t["Block"]["Time"],
        })

    return results


def _fetch_bitcoin_whales(since: str, till: str) -> list[dict]:
    """
    Bitcoin 체인의 대형 트랜잭션을 Bitquery로 조회.
    """
    if "BTC" not in WHALE_TRACKED_SYMBOLS:
        return []

    min_usd = WHALE_MIN_VALUE_USD

    query = """
    query WhaleBTC($since: ISO8601DateTime, $till: ISO8601DateTime, $minUsd: Float) {
      bitcoin {
        transactions(
          options: {limit: 30, desc: "block.timestamp.time"}
          date: {since: $since, till: $till}
          outputCountGt: 0
        ) {
          block {
            timestamp {
              time(format: "%Y-%m-%dT%H:%M:%SZ")
            }
          }
          hash
          outputValue
          outputValueUsd
          inputAddress {
            address
          }
          outputAddress {
            address
          }
        }
      }
    }
    """

    try:
        resp = httpx.post(
            BITQUERY_API_URL,
            headers={
                "Authorization": f"Bearer {BITQUERY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "variables": {
                    "since": since,
                    "till": till,
                    "minUsd": min_usd,
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[고래감시-BTC] ⚠️ API 오류: {e}")
        return []

    if "errors" in data:
        print(f"[고래감시-BTC] ⚠️ GraphQL 에러: {data['errors']}")
        return []

    txs = data.get("data", {}).get("bitcoin", {}).get("transactions", [])
    results = []

    for tx in txs:
        usd_val = float(tx.get("outputValueUsd") or 0)
        if usd_val < min_usd:
            continue

        from_addr = (tx.get("inputAddress") or [{}])[0].get("address", "unknown")
        to_addr = (tx.get("outputAddress") or [{}])[0].get("address", "unknown")

        results.append({
            "blockchain": "bitcoin",
            "symbol": "BTC",
            "amount": float(tx.get("outputValue") or 0),
            "amount_usd": usd_val,
            "from_address": from_addr,
            "to_address": to_addr,
            "from_label": "unknown",
            "to_label": "unknown",
            "tx_hash": tx["hash"],
            "whale_alert_id": tx["hash"][:16],
            "occurred_at": tx["block"]["timestamp"]["time"],
        })

    return results


def fetch_whale_transactions() -> list[dict]:
    """
    Bitquery API에서 대형 거래 목록을 가져오는 함수.
    EVM (ETH/USDT/USDC) + BTC 를 병렬 조회.
    """
    global _last_cursor_time

    since, till = _get_time_range()
    print(f"[고래감시] Bitquery 조회 범위: {since} ~ {till}")

    # EVM + BTC 동시 조회
    evm_txs = _fetch_evm_whales(since, till)
    btc_txs = _fetch_bitcoin_whales(since, till)

    all_txs = evm_txs + btc_txs
    print(f"[고래감시] Bitquery 응답: EVM {len(evm_txs)}건 + BTC {len(btc_txs)}건 = 총 {len(all_txs)}건")

    # 다음 호출을 위해 마지막 조회 시간 업데이트
    _last_cursor_time = datetime.now(timezone.utc)

    return all_txs


def filter_new_transactions(transactions: list[dict]) -> list[dict]:
    """
    이미 DB에 저장된 거래를 제외하고, 새 거래만 반환하는 함수.
    tx_hash를 기준으로 중복 체크한다.
    """
    if not transactions:
        return []

    tx_hashes = [tx["tx_hash"] for tx in transactions if tx["tx_hash"]]

    if not tx_hashes:
        return transactions

    try:
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
    """
    if not transactions:
        return []

    saved = []

    for tx in transactions:
        try:
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
                "push_sent": False,
            }

            result = supabase.table("whale_alerts").insert(row).execute()

            if result.data:
                saved_row = result.data[0]
                tx["id"] = saved_row["id"]
                saved.append(tx)
                print(
                    f"[고래감시] ✅ 저장: {tx['symbol']} "
                    f"{tx['amount']:,.2f}개 (${tx['amount_usd']:,.0f})"
                )

        except Exception as e:
            print(f"[고래감시] ⚠️ 저장 실패 ({tx['tx_hash'][:12]}...): {e}")
            continue

    print(f"[고래감시] 총 {len(saved)}건 신규 저장 완료")
    return saved


def get_unsent_alerts() -> list[dict]:
    """
    이전 주기에서 푸시 발송에 실패한 건(push_sent=false)을 DB에서 조회하는 함수.
    """
    try:
        result = (
            supabase.table("whale_alerts")
            .select("id, blockchain, symbol, amount, amount_usd, "
                    "from_address, to_address, from_label, to_label, "
                    "tx_hash, whale_alert_id, occurred_at")
            .eq("push_sent", False)
            .order("occurred_at", desc=True)
            .limit(50)
            .execute()
        )

        unsent = result.data or []
        if unsent:
            print(f"[고래감시] 📋 미발송 건 {len(unsent)}건 발견")
        return unsent

    except Exception as e:
        print(f"[고래감시] ⚠️ 미발송 건 조회 실패: {e}")
        return []


def run_whale_check() -> list[dict]:
    """
    고래 감시의 메인 실행 함수.
    main.py의 APScheduler가 5분마다 이 함수를 호출한다.
    """
    print()
    print("=" * 50)
    print(f"[고래감시] 🐋 감시 시작: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("[고래감시] 데이터 소스: Bitquery API (무료)")
    print("=" * 50)

    # 1단계: Bitquery API에서 거래 가져오기
    transactions = fetch_whale_transactions()

    # 2단계: 중복 제거 + DB 저장
    if transactions:
        new_transactions = filter_new_transactions(transactions)
        if new_transactions:
            save_to_database(new_transactions)
        else:
            print("[고래감시] 모두 이미 저장된 거래")
    else:
        print("[고래감시] 조회 기간 내 $100만+ 거래 없음")

    # 3단계: 미발송 건 전부 조회 (이번 신규 + 이전 실패분)
    unsent_alerts = get_unsent_alerts()

    if not unsent_alerts:
        print("[고래감시] 발송 대기 건 없음 — 다음 주기에 재확인")
        return []

    print(f"[고래감시] 🐋 감시 완료: 발송 대기 {len(unsent_alerts)}건")
    return unsent_alerts
