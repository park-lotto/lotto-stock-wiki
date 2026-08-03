"""제품명 선판독(백필) — 조회수 상위부터 미리 읽어둔다 (2026-08-04).

■ 왜 (실측 근거)
검색을 누를 때만 판독하는 방식은 사장님 지시대로 만들었고 잘 돈다. 하지만
축적 속도가 느려 후보풀 4,611건 중 제품명 보유가 **276건(6%)**뿐이었다.
그 상태에선 검색 로직을 고쳐도 효과가 안 난다(전후 비교 실측: 13건 → 15건, +2).
재료가 없으면 로직이 논다.

그래서 **조회수 상위부터** 미리 판독해 재료를 깐다. 전량(14,000건)을 태우자는
얘기가 아니다 — 사장님이 실제로 검색할 영역은 상위권이므로 거기만 채운다.

■ 안전장치 (밤새 무인 실행 전제)
- 렌더·믹스가 돌면 양보(heavy_job_running) — 크롤러·태거와 같은 원칙.
- 디스크 여유가 임계 미만이면 즉시 중단(2026-08-04에 디스크가 차서 태거·크롤러가
  [Errno 28]로 죽은 실사고가 있었다. 같은 걸 밤새 반복하면 안 된다).
- 키가 전부 소진되면 조용히 멈춘다(무한 재시도 금지).
- 이미 판독된 건 건너뛴다(identify_many가 캐시를 본다) → 재실행이 안전하다.
- 배치마다 진행률을 찍는다 → 아침에 로그만 봐도 어디까지 됐는지 안다.

실행:
    python -m shopping_shorts.product_backfill --top 3000
    python -m shopping_shorts.product_backfill --top 3000 --batch 40
"""
import argparse
import shutil
import time

from shopping_shorts import product_name
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store

_MIN_FREE_GB = 3.0      # 이보다 적으면 중단 — 디스크 풀로 다른 작업까지 죽는 걸 막는다
_BUSY_POLL_S = 60
_MAX_YIELD_S = 1800     # 렌더 양보 상한 30분 — 무한대기 금지
_STALE_HEARTBEAT_S = 900   # 심박 15분 끊기면 죽은 잡으로 본다


def _render_alive(store, log=print):
    """진짜로 렌더가 도는 중인가. store.heavy_job_running()을 그대로 쓰면 안 된다.

    실측(2026-08-04): job_queue에 task='clean'이 state='running'인 채 **8시간째**
    박혀 있었다(heartbeat 18:00에서 멈춤, 실제 ffmpeg·remotion 프로세스 없음).
    그대로 믿으면 백필이 밤새 '렌더 진행 중'만 찍고 한 건도 안 한다(실제로 그랬다).
    → 심박이 끊긴 잡은 죽은 것으로 보고 무시한다. 살아있는 잡에만 양보한다."""
    try:
        with store._conn() as c:
            n = c.execute(
                "SELECT COUNT(*) FROM job_queue WHERE state='running' "
                "AND task IN ('render','mix','retype','preview','clean') "
                "AND heartbeat_at IS NOT NULL "
                "AND (julianday('now') - julianday(heartbeat_at)) * 86400 < ?",
                (_STALE_HEARTBEAT_S,)).fetchone()[0]
        return n > 0
    except Exception as e:      # noqa: BLE001 — 판정 실패 시 양보하지 않는다(멈추는 것보다 낫다)
        log(f"[백필] 렌더 판정 실패(무시하고 진행): {str(e)[:60]}")
        return False


def pick_targets(store, top, offset=0):
    """조회수 상위에서 '아직 제품명이 없는' 릴스 [{shortcode, thumbnail}]."""
    with store._conn() as c:
        rows = c.execute(
            "SELECT a.shortcode, a.thumbnail, a.views FROM channel_archive a "
            "LEFT JOIN vision_tags v ON v.shortcode=a.shortcode "
            "WHERE a.thumbnail!='' AND (v.product_at IS NULL) "
            "ORDER BY a.views DESC LIMIT ? OFFSET ?", (top, offset)).fetchall()
    return [{"shortcode": r[0], "thumbnail": r[1], "views": r[2] or 0} for r in rows]


def _free_gb(path="/"):
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except Exception:      # noqa: BLE001 — 못 재면 막지 않는다(윈도 로컬 등)
        return 999.0


def run(top=3000, batch=40, sleep=time.sleep, log=print):
    store = Store(DB_PATH)
    done = 0
    empty_rounds = 0
    t0 = time.time()
    while done < top:
        free = _free_gb()
        if free < _MIN_FREE_GB:
            log(f"[백필] 디스크 여유 {free:.1f}GB < {_MIN_FREE_GB}GB — 중단(재실행하면 이어짐)")
            break
        waited = 0
        while _render_alive(store, log):        # 렌더에 양보(단, 죽은 잡은 무시)
            log(f"[백필] 렌더 진행 중 → {_BUSY_POLL_S}s 대기")
            sleep(_BUSY_POLL_S)
            waited += _BUSY_POLL_S
            if waited >= _MAX_YIELD_S:
                log(f"[백필] {_MAX_YIELD_S//60}분째 대기 — 그만 기다리고 진행한다")
                break

        targets = pick_targets(store, min(batch, top - done))
        if not targets:
            log("[백필] 판독할 게 없다 — 완료")
            break

        before = len(store.products_map([t["shortcode"] for t in targets]))
        pmap = product_name.identify_many(targets, DB_PATH)
        got = len(pmap) - before
        done += len(targets)
        if got <= 0:
            empty_rounds += 1
            # 키 소진·썸네일 만료가 겹치면 계속 0이 나온다. 3회 연속이면 멈춘다.
            if empty_rounds >= 3:
                log("[백필] 3배치 연속 0건 — 키 소진 또는 썸네일 만료로 판단, 중단")
                break
        else:
            empty_rounds = 0
        el = time.time() - t0
        named = sum(1 for v in pmap.values() if v)
        log(f"[백필] {done}/{top}  이번배치 +{got}건(제품명 있음 {named})  "
            f"경과 {el/60:.1f}분  여유 {free:.1f}GB")
    log(f"[백필] 종료 — {done}건 처리, {(time.time()-t0)/60:.1f}분")
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=3000, help="조회수 상위 몇 건까지")
    ap.add_argument("--batch", type=int, default=40)
    a = ap.parse_args()
    run(top=a.top, batch=a.batch)


if __name__ == "__main__":
    main()
