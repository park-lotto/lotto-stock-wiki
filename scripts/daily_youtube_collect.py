"""유튜브 자동수집(무료 경로) — systemd 타이머가 하루 6번 깨우고, **반나절에 한 번**만 실제로 돈다.

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

DONE_KEY = "daily_collect_done::youtube"   # 값 = 마지막으로 성공한 회차(KST, YYYY-MM-DD-AM|PM)


def main():
    t0 = time.time()
    # ★렌더 양보(2026-07-30) — 유튜브 수집은 API라 가볍지만, 렌더가 도는 1GB 서버에선
    # 파이썬 프로세스 하나도 swap을 밀어낸다. 양보하되 오늘 안에 반드시 다시 온다(아래).
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    store = Store(DB_PATH)
    # ★회원 유튜브 키를 공용 풀에 합류시킨다(2026-09-09 사장님 "고객들 유튭키가 다
    #   공용이야 전체 회원키로 레퍼런스랭킹하는거야 그걸로 수집해").
    #
    #   이 스크립트는 **별도 프로세스**라 FastAPI startup이 없다 — 그래서 회원 키를
    #   하나도 모른 채 사장님 키 10개로만 돌았다. 실측 2026-09-09:
    #     회원 유튜브 키 52개가 DB에 등록돼 있는데 수집은 10개만 사용
    #     → 쓸 수 있는 하루 쿼터 620,000 units 중 100,000만 쓰고 "소진"으로 멈춤
    #     → 시드 2,170개 중 1,020개만 응답(영상 9,622→7,323 · 썰쇼핑 813→526)
    #
    #   ⚠️2026-08-31에 **똑같은 사고**가 워커에서 났고(회원 키 44개를 통째로 몰랐다)
    #     그때 웹·워커·capacity_watch는 고쳤는데 이 스크립트와 발굴 루프는 빠져 있었다.
    #     keypool.resync_pools가 합류 규칙의 유일한 출처다(0순위-B) — 여기 다시 적지 않는다.
    try:
        from shopping_shorts import keypool
        keypool.resync_pools(store, verbose=True)
    except Exception as e:      # noqa: BLE001 — 합류 실패가 수집을 막지 않는다
        print(f"[daily_youtube_collect] 회원키 합류 실패(사장님 키로 계속): {e!r}",
              file=sys.stderr)
    # ★하루치 중복 방지 + 재시도(2026-08-31): 예전엔 타이머가 하루 1회뿐이라, 그 순간
    #   렌더가 돌면 "다음 회차로 미룬다"면서 실제로는 **그날 수집이 통째로 날아갔다**
    #   (실사고 08-31: 08:10에 렌더 중 → 스킵 → 하루 0건, 사장님이 발견).
    #   낮에 제작을 계속하면 렌더 중일 확률이 높아 구조적으로 재발한다.
    #   그래서 타이머를 여러 시각으로 늘리고, 성공한 날은 이 표식으로 건너뛴다.
    # ★하루 1회 → **반나절 1회**로 늘린다 (2026-09-10 사장님 "수집을 늘리고 싶다").
    #   왜: 12시간 히트작 탭을 붙였는데 수집이 하루 1회면 그 뒤 12시간이 지나는 순간
    #   '올라온 지 12시간 이내'가 0건이 된다 — 저녁부터 탭이 통째로 빈다.
    #
    #   쿼터가 되는가(2026-09-10 서버 실측):
    #     유튜브 키 62개(사장님 10 + 회원 52) = 하루 620,000 units
    #     시드 2,386개 × 검색 100 units = 회당 약 238,600 units
    #     → 1회 38% · **2회 77%** · 3회 115%(초과). 그래서 2회까지만 연다.
    #   시간도 든다: 실측 1회 77분(08:10~09:27, 9,983건).
    #
    #   경계를 14시로 둔 이유 — 오후 슬롯에 재시도 기회를 4번(14:10·17:10·20:10·22:40)
    #   남기기 위해서다. 08-31 실사고처럼 렌더와 겹쳐 한 번 양보하면 그 슬롯이 통째로
    #   날아가는데, 기회가 하나뿐이면 그게 곧 '그 반나절 0건'이 된다.
    _now = datetime.now(ZoneInfo("Asia/Seoul"))
    slot = _now.strftime("%Y-%m-%d") + ("-AM" if _now.hour < 14 else "-PM")
    if store.get_setting(DONE_KEY) == slot:
        print(f"[daily_youtube_collect] 이번 회차({slot}) 이미 수집 완료 — 건너뜀")
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
    store.set_setting(DONE_KEY, slot)    # 이번 반나절 완료 — 남은 회차는 건너뛴다
    print(f"[daily_youtube_collect] {len(items)}건 수집 · {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
