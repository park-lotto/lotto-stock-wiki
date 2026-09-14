"""썰쇼핑 채널만 3시간마다 다시 긁어 유튜브 랭킹에 합친다 (2026-09-14 사장님 "썰만 3시간 한번씩").

왜: 전체 유튜브 수집(daily_youtube_collect)은 반나절 1회라, 12시간 히트작 탭의
    썰쇼핑이 1건뿐이었다(실측 09-14 11:57 — 12h 1 · 24h 30 · 48h 66).

비용: 채널 시드 경로는 search.list(100u)가 아니라 playlistItems(1u)+videos.list(1u)
      = 채널당 2 units. 썰쇼핑 채널 ~236개면 회당 ~500 units(하루 8회 ~4,000).

대상 채널 = 지금 랭킹(last_run::youtube)에서 썰쇼핑(제품정체형·오용형) 영상을 낸 채널.
저장 = store.merge_last_run_platform(update_existing=True) — 한 트랜잭션에서 합치고
       옛 항목 age_hours를 collected_at이 밀린 만큼 보정한다. 여기서 따로 저장하지 않는다.
save_run_platform(조회수 기준선)은 안 건드린다 — 가속(delta)은 전체 수집이 정한다.
"""
import subprocess
import sys
import time
from datetime import datetime, timezone

from shopping_shorts.config import DB_PATH, YOUTUBE_WINDOW_HOURS
from shopping_shorts.store import Store

SSUL_CATEGORIES = ("제품정체형", "오용형")   # index.html 카테고리 라벨 '썰쇼핑'과 짝


def _main_collect_running():
    try:
        r = subprocess.run(["systemctl", "is-active", "shopping-shorts-collect.service"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() in ("active", "activating")
    except Exception:           # noqa: BLE001 — systemctl 없는 환경(로컬)
        return False


def main():
    t0 = time.time()
    store = Store(DB_PATH)
    if _main_collect_running():
        print("[ssul_refresh] 전체 유튜브 수집 진행 중 — 건너뜀")
        return 0
    # ★건너뛰지 말고 기다린다(2026-09-14 실측: 12:26·12:40 두 번 연속 렌더 중 스킵).
    #   낮엔 렌더가 거의 늘 돌아 '스킵'이면 3시간 갱신이 사실상 안 돈다.
    #   이 작업은 API 호출뿐이라 가볍다 — 최대 40분 기다린 뒤엔 그냥 돈다.
    waited = 0
    while store.heavy_job_active() and waited < 40 * 60:
        time.sleep(60)
        waited += 60
    if waited:
        print(f"[ssul_refresh] 렌더 양보 {waited // 60}분 대기 후 진행")
    try:
        from shopping_shorts import keypool
        keypool.resync_pools(store, verbose=False)
    except Exception as e:      # noqa: BLE001
        print(f"[ssul_refresh] 회원키 합류 실패(사장님 키로 계속): {e!r}", file=sys.stderr)

    from shopping_shorts import ranking
    from shopping_shorts.youtube_client import fetch_channel_shorts, fetch_subscribers

    prev, _ = store.load_last_run_platform("youtube")
    channels = sorted({i.get("username") for i in prev
                       if i.get("category") in SSUL_CATEGORIES and i.get("username")})
    if not channels:
        print("[ssul_refresh] 썰쇼핑 채널 0개 — 할 일 없음")
        return 0

    raw = []
    for cid in channels:
        raw.extend(fetch_channel_shorts(f"https://www.youtube.com/channel/{cid}"))
    seen, deduped = set(), []
    for r in raw:
        v = r.get("video_id")
        if v and v not in seen:
            seen.add(v)
            deduped.append(r)
    now = datetime.now(timezone.utc)
    subs = fetch_subscribers([r.get("channel_id") for r in deduped])
    items = ranking.build_youtube_items(
        deduped,
        prev_base=lambda sc: store.prev_base_platform("youtube", sc),
        prev_delta=lambda sc: store.prev_delta_platform("youtube", sc),
        now=now, window_hours=YOUTUBE_WINDOW_HOURS, subs=subs,
    )
    # 등급은 전체 모집단 안에서 매긴 값이라, 일부만 다시 매기면 부풀어 오른다.
    # 이미 있던 영상은 전체 수집이 준 등급을 그대로 이어받고, 새 영상만 새로 매긴다.
    ranking.apply_grades(items)
    prev_grade = {i.get("shortcode"): i.get("grade") for i in prev}
    for i in items:
        if prev_grade.get(i["shortcode"]):
            i["grade"] = prev_grade[i["shortcode"]]
    if not items:
        print(f"[ssul_refresh] 채널 {len(channels)}개에서 0건 — 저장 안 함(쿼터·네트워크 확인)")
        return 1
    added, total = store.merge_last_run_platform("youtube", items, now.isoformat(),
                                                 update_existing=True)
    n12 = sum(1 for i in items if i.get("category") in SSUL_CATEGORIES
              and (i.get("age_hours") or 1e9) <= 12)
    print(f"[ssul_refresh] 채널 {len(channels)} · 영상 {len(items)}건(신규 {added}) · "
          f"썰쇼핑 12h {n12}건 · 전체 {total} · {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
