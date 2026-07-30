"""인스타 레퍼런스랭킹 자동수집(무료 Playwright 경로) — systemd 타이머가
하루 3회(09/15/21시 KST) 실행(2026-07-29).

앱 HTTP를 거치지 않고 service.collect(platform="instagram")를 직접 호출한다.
- 인증/페이월 우회(관리자 세션 불필요)
- 앱과 같은 DB(config.DB_PATH, 모듈 기준 고정경로)에 run 스냅샷 저장 →
  다음 조회 시 랭킹·가속(delta)이 갱신돼 있음.
config.INSTAGRAM_SCRAPER가 playwright면 무료(세션쿠키+서버직결), apify면 유료 —
이 스크립트는 값을 강제하지 않고 서버 env(/etc/shopping-shorts.env) 설정을 그대로 따른다.
"""
import sys
import time

from shopping_shorts import service


def main():
    t0 = time.time()
    try:
        items = service.collect(platform="instagram")
    except Exception as e:  # noqa: BLE001 — 크론이 죽어도 서비스는 무사, 로그만 남긴다
        print(f"[daily_instagram_collect] 실패: {e!r}", file=sys.stderr)
        return 1
    print(f"[daily_instagram_collect] {len(items)}건 수집 · {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
