"""인스타 신규채널 발굴(무료 Playwright 경로) — systemd 타이머가 하루 1회
07:00 KST 실행(2026-07-30). 09:00 레퍼런스랭킹 자동수집(daily_instagram_collect)
보다 2시간 앞서 돌려, 발굴된 신규 채널이 09시 수집부터 바로 반영되게 한다.

앱 HTTP를 거치지 않고 discover_jobs._run()을 직접 동기 호출한다(백그라운드
스레드로 감쌀 필요 없음 — 이 스크립트 자체가 이미 크론이 띄운 별도 프로세스).
등록은 자동이 아니라 화면의 [목록추가] 버튼으로 사람이 고른다(2026-08-03 전환 —
7/30~8/2 자동등록 기간의 일 19~45건이 전부 목록에 쌓여 피드가 온통 '추가됨'이 됐다).
"""
import sys
import time

from shopping_shorts import discover_jobs

MAX_TOTAL = 300   # 2026-07-30: 120→300(사장님 지시, 무료 전환 후 과금 걱정 없어 확대)
DAYS = 2          # 최근 이틀 이내 릴스만 발굴 대상(기존 화면 기본값과 동일)


def main():
    t0 = time.time()
    # ★렌더 양보(2026-07-30) — 발굴은 태그마다 Playwright를 띄워 제일 무겁다.
    # 렌더 중이면 건너뛴다(누적이라 한 회차 스킵은 손실이 아니다).
    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    if Store(DB_PATH).heavy_job_active():
        print("[daily_instagram_discover] 렌더/믹스 진행 중 — 이번 회차 스킵")
        return 0
    with discover_jobs._LOCK:
        discover_jobs._JOB.update(status="running", phase="시작", count=0, items=[],
                                  error=None, started=t0, registered=0)
    try:
        # auto_register=False(2026-08-03 사장님 지시) — 자동등록을 켜니 발굴 전부가
        # 추적목록에 들어가 피드가 온통 '추가됨'이 됐다. 발굴은 후보만 보여주고,
        # 등록은 사람이 [목록추가]로 고른다(누르면 피드에서 사라짐).
        discover_jobs._run(DAYS, MAX_TOTAL, accumulate=False, auto_register=False)
    except Exception as e:  # noqa: BLE001 — 크론이 죽어도 서비스는 무사, 로그만 남긴다
        print(f"[daily_instagram_discover] 실패: {e!r}", file=sys.stderr)
        return 1
    st = discover_jobs.status(include_items=False)
    if st.get("status") == "error":
        print(f"[daily_instagram_discover] 실패: {st.get('error')}", file=sys.stderr)
        return 1
    print(f"[daily_instagram_discover] {st.get('count')}건 발굴 · "
          f"{st.get('registered')}건 자동등록 · "
          f"인물채널 {st.get('skipped_face', 0)}건 제외 · {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
