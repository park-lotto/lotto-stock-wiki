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


_TRIED_RETRY_DAYS = 7   # 만료 썸네일 실패 기록 후 재시도 유예 — 재크롤로 URL이 갱신될 시간

def _ensure_tried_table(store):
    with store._conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS product_backfill_tried("
                  "shortcode TEXT PRIMARY KEY, tried_at TEXT NOT NULL)")


def _mark_tried(store, shortcodes):
    if not shortcodes:
        return
    with store._conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO product_backfill_tried(shortcode, tried_at) "
            "VALUES(?, datetime('now'))", [(sc,) for sc in shortcodes])


def pick_targets(store, top, offset=0):
    """조회수 상위에서 '아직 제품명이 없는' 릴스 [{shortcode, thumbnail}]."""
    with store._conn() as c:
        rows = c.execute(
            "SELECT a.shortcode, a.thumbnail, a.views FROM channel_archive a "
            "LEFT JOIN vision_tags v ON v.shortcode=a.shortcode "
            "LEFT JOIN product_backfill_tried t ON t.shortcode=a.shortcode "
            "WHERE a.thumbnail!='' AND (v.product_at IS NULL) "
            "AND (t.tried_at IS NULL OR "
            "     (julianday('now') - julianday(t.tried_at)) > " + str(_TRIED_RETRY_DAYS) + ") "
            "ORDER BY a.views DESC LIMIT ? OFFSET ?", (top, offset)).fetchall()
    return [{"shortcode": r[0], "thumbnail": r[1], "views": r[2] or 0} for r in rows]


def _done_count(store):
    """지금까지 판독된 총 건수(product_at 기준). 배치 진척 판정의 진실."""
    with store._conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM vision_tags WHERE product_at IS NOT NULL").fetchone()[0]


def _free_gb(path="/"):
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except Exception:      # noqa: BLE001 — 못 재면 막지 않는다(윈도 로컬 등)
        return 999.0


def run(top=3000, batch=40, sleep=time.sleep, log=print):
    store = Store(DB_PATH)
    _ensure_tried_table(store)
    done = 0
    skipped = 0        # 만료 등으로 저장 안 된 누적분 — offset으로 건너뛴다
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

        # offset을 쓰는 이유: 썸네일이 만료된 건 저장이 안 돼 product_at이 계속 NULL이라
        # 같은 행이 매 배치 또 뽑힌다(=영원히 제자리). 처리한 만큼 건너뛴다.
        targets = pick_targets(store, min(batch, top - done), offset=skipped)
        if not targets:
            log("[백필] 판독할 게 없다 — 완료")
            break

        # 진척은 **DB의 product_at 개수**로 잰다(2026-08-04 수정).
        # 처음엔 pmap 길이로 쟀는데, pick_targets가 이미 product_at IS NULL만 고르므로
        # before는 항상 0이고 got==len(pmap)이 된다. 썸네일이 만료된 배치에서는 아무것도
        # 저장되지 않아 pmap이 비고 → '3배치 연속 0건'으로 **정상 동작 중에 멈췄다**
        # (실측: 160건에서 조기중단. 실제로는 판독·저장이 잘 되고 있었다).
        # 만료 썸네일은 저장 대상이 아니므로 그 배치가 0인 건 정상이다 — 그래도 커서는
        # 앞으로 가야 다음 배치로 넘어간다.
        prev_total = _done_count(store)
        expired = []    # 썸네일 만료로 영구실패한 행 — 기록해서 다음 실행이 건너뛰게 한다(2026-08-09)
        pmap = product_name.identify_many(targets, DB_PATH, expired_out=expired)
        got = _done_count(store) - prev_total
        _mark_tried(store, expired)
        done += len(targets)
        skipped += max(0, len(targets) - got)   # 저장 안 된 만큼 다음 배치에서 건너뛴다
        if got <= 0:
            empty_rounds += 1
            # 진짜로 아무것도 못 저장하는 상태(키 전멸·전부 만료)가 이어지면 멈춘다.
            # 6배치로 잡은 이유: 만료 썸네일이 연달아 몇 배치 나오는 건 흔하다.
            if empty_rounds >= 6:
                log("[백필] 6배치 연속 0건 — 키 소진 또는 썸네일 만료 구간으로 판단, 중단")
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
