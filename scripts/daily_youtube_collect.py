"""매일 유튜브 자동수집(무료 경로) — systemd 타이머가 하루 여러 번 실행, 성공하면 그날은 끝.

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

DONE_KEY = "daily_collect_done::youtube"   # 값 = 마지막으로 수집에 성공한 날짜(KST, YYYY-MM-DD)


def main():
    t0 = time.time()
    # ★렌더 양보(2026-07-30) — 유튜브 수집은 API라 가볍지만, 렌더가 도는 1GB 서버에선
    # 파이썬 프로세스 하나도 swap을 밀어낸다. 양보하되 오늘 안에 반드시 다시 온다(아래).
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    store = Store(DB_PATH)
    # ★하루치 중복 방지 + 재시도(2026-08-31): 예전엔 타이머가 하루 1회뿐이라, 그 순간
    #   렌더가 돌면 "다음 회차로 미룬다"면서 실제로는 **그날 수집이 통째로 날아갔다**
    #   (실사고 08-31: 08:10에 렌더 중 → 스킵 → 하루 0건, 사장님이 발견).
    #   낮에 제작을 계속하면 렌더 중일 확률이 높아 구조적으로 재발한다.
    #   그래서 타이머를 여러 시각으로 늘리고, 성공한 날은 이 표식으로 건너뛴다.
    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    if store.get_setting(DONE_KEY) == today:
        print(f"[daily_youtube_collect] 오늘({today}) 이미 수집 완료 — 건너뜀")
        return 0
    if store.heavy_job_active():
        print("[daily_youtube_collect] 렌더/믹스 진행 중 — 다음 회차에 재시도")
        return 0
    try:
        # ⚠️ seed_only는 아직 켜지 않는다 (2026-07-29).
        # 켜면 키워드 경로가 빠져 '등록된 계정 시드'만 남는데, 랭킹에 등장하는 채널 715개 중
        # 시드에 등록된 건 464개뿐이다. 미등록 우량 채널을 먼저 시드에 넣지 않고 켜면
        # 수집량이 급감한다(설계 §T3이 §T4보다 먼저인 이유).
        # 켜는 순서: scripts/register_good_youtube_channels.py 실행 → 시드 보강 확인
        #            → 여기를 seed_only=True 로 → 1회 수집 후 '기타' 비율 실측(목표 20% 미만).
        items = service.collect(platform="youtube")
    except Exception as e:  # noqa: BLE001 — 크론이 죽어도 서비스는 무사, 로그만 남긴다
        print(f"[daily_youtube_collect] 실패: {e!r}", file=sys.stderr)
        return 1
    store.set_setting(DONE_KEY, today)   # 오늘치 완료 — 남은 회차는 건너뛴다
    print(f"[daily_youtube_collect] {len(items)}건 수집 · {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
