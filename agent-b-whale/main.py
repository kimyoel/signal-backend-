"""
main.py — 에이전트 B 엔트리포인트 (시작점)

쉽게 말하면: 이 파일을 실행하면 에이전트 B가 시작된다.
5분마다 자동으로 고래 거래를 확인하고, 새 거래가 있으면 알림을 보낸다.

실행 방법:
    python main.py

동작 방식:
    1. 환경변수 확인 (API 키들이 제대로 설정됐는지)
    2. APScheduler 시작 (5분 주기 타이머)
    3. 5분마다 → whale_monitor 실행 → push_sender 실행
    4. Ctrl+C로 종료할 때까지 계속 실행
"""

import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler

from config import POLLING_INTERVAL_SECONDS, validate_config
from whale_monitor import run_whale_check
from push_sender import send_whale_alerts


def whale_job():
    """
    5분마다 실행되는 작업 함수.

    순서:
    1. 고래 거래 확인 (API 호출 → 중복 제거 → DB 저장)
    2. 새 거래가 있으면 푸시 알림 발송
    """
    try:
        # 1. 고래 거래 확인
        new_whales = run_whale_check()

        # 2. 새 거래가 있으면 알림 발송
        if new_whales:
            send_whale_alerts(new_whales)
        else:
            print("[메인] 이번 주기: 신규 거래 없음 ✓")

    except Exception as e:
        # 에러가 나도 스케줄러는 죽지 않음 (다음 5분에 다시 시도)
        print(f"[메인] ⚠️ 작업 중 에러 발생: {e}")
        import traceback
        traceback.print_exc()


def graceful_shutdown(signum, frame):
    """
    Ctrl+C 또는 서버 종료 시 깔끔하게 마무리하는 함수.
    Railway에서 서비스를 재배포할 때도 이 함수가 호출됨.
    """
    print()
    print("=" * 50)
    print("[메인] 🛑 종료 신호 수신 — 에이전트 B를 종료합니다")
    print("=" * 50)
    sys.exit(0)


def main():
    """
    에이전트 B의 메인 실행 함수.
    """
    print()
    print("╔══════════════════════════════════════════╗")
    print("║   🐋 SIGNAL 에이전트 B — 고래 알림 시스템   ║")
    print("║   v1.0 | 2026.03.14                      ║")
    print("╚══════════════════════════════════════════╝")
    print()

    # 1. 환경변수 확인
    print("[메인] 환경변수 확인 중...")
    if not validate_config():
        print("[메인] ❌ 필수 환경변수가 없어서 시작할 수 없습니다.")
        print("[메인] .env.example을 참고해서 .env 파일을 만들어주세요.")
        sys.exit(1)

    # 2. 종료 시그널 처리 등록 (Ctrl+C 누르면 깔끔하게 종료)
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # 3. 첫 실행: 시작하자마자 한 번 체크 (5분 안 기다리고)
    print()
    print(f"[메인] 🚀 첫 번째 감시 실행 (이후 {POLLING_INTERVAL_SECONDS}초마다 반복)")
    whale_job()

    # 4. 스케줄러 설정 (5분마다 반복)
    scheduler = BlockingScheduler()
    scheduler.add_job(
        whale_job,
        "interval",
        seconds=POLLING_INTERVAL_SECONDS,
        id="whale_check",
        name="고래 거래 감시",
        max_instances=1,  # 이전 작업이 안 끝났으면 다음 실행 건너뛰기
    )

    print()
    print(f"[메인] ⏰ 스케줄러 시작 — {POLLING_INTERVAL_SECONDS}초(={POLLING_INTERVAL_SECONDS//60}분) 간격")
    print("[메인] 종료하려면 Ctrl+C를 누르세요")
    print()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[메인] 스케줄러 종료됨")


if __name__ == "__main__":
    main()
