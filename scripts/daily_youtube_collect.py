"""매일 유튜브 자동수집(무료 경로) — systemd 타이머가 하루 1회 실행.

앱 HTTP를 거치지 않고 service.collect(platform="youtube")를 직접 호출한다.
- 인증/페이월 우회(관리자 세션 불필요)
- 앱과 같은 DB(config.DB_PATH, 모듈 기준 고정경로)에 run 스냅샷 저장 →
  다음 조회 시 랭킹·가속(delta)이 갱신돼 있음.
유튜브 계정·키워드·카테고리 프리셋 시드는 전부 무료(Data API 쿼터/검색).
인스타(Apify 유료)는 건드리지 않는다.
"""
import sys
import time

from shopping_shorts import service


def main():
    t0 = time.time()
    try:
        items = service.collect(platform="youtube")
    except Exception as e:  # noqa: BLE001 — 크론이 죽어도 서비스는 무사, 로그만 남긴다
        print(f"[daily_youtube_collect] 실패: {e!r}", file=sys.stderr)
        return 1
    print(f"[daily_youtube_collect] {len(items)}건 수집 · {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
