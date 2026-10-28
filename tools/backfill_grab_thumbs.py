"""담기 항목의 빈 썸네일·이름을 다시 받아 채운다(바구니 + 작업 handoff 복사본 양쪽).

왜 필요한가 (2026-09-21)
------------------------
`_ig_cookies_file()`이 하위 폴더의 살아있는 세션 풀을 못 봐서(최상위 glob) 6주 묵은
죽은 인스타 세션을 골랐고, 그동안 담긴 항목은 **저장 시점에 이미 빈 값**이 됐다.
코드는 고쳤지만 **이미 비어버린 과거분은 자동으로 안 채워진다** — 이 도구가 채운다.

두 곳을 함께 고쳐야 화면이 산다 (실측으로 확인한 것)
---------------------------------------------------
  1) mix_basket.thumbnail/name        ← 즐겨찾기 카드가 읽는 곳
  2) produce_works.state_json.handoff ← **제작소 씨앗 카드가 읽는 곳**
`grab_*` 항목은 script_wiki·reel_history에 행이 없어서(실측 0건) _load_work_sources의
`w`가 None이 되고, 썸네일은 전적으로 handoff 복사본에서 나온다. 그래서 바구니만
채우면 이미 만들어진 작업 화면은 **그대로 회색**이다.

사용법
------
    python tools/backfill_grab_thumbs.py --dry-run          # 무엇을 고칠지만 본다
    python tools/backfill_grab_thumbs.py --days 14          # 실제로 고친다
    python tools/backfill_grab_thumbs.py --work e285b3705796  # 한 작업만

⚠️ 서버에서 env를 실어 돌려라 — 안 그러면 세션 경로를 못 찾아 전부 실패로 보인다:
    set -a && . /etc/shopping-shorts.env && set +a && sudo -E python3 tools/backfill_grab_thumbs.py
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _db_path():
    for p in ("shopping_shorts/data/reference.db", "shopping_shorts/data/app.db"):
        if Path(p).exists():
            return p
    raise SystemExit("DB를 못 찾았다 — 저장소 루트에서 실행하라")


def _probe(url, cache):
    """URL → {thumbnail,title}. 같은 URL을 두 번 묻지 않는다."""
    if url in cache:
        return cache[url]
    from shopping_shorts.media_download import probe_grab_meta
    try:
        meta = probe_grab_meta(url) or {}
    except Exception as e:  # noqa: BLE001 — 한 건 실패가 전체를 멈추면 안 된다
        print("    probe 예외 %s: %r" % (url[-16:], e))
        meta = {}
    cache[url] = meta
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14, help="최근 N일 작업만(기본 14)")
    ap.add_argument("--work", default="", help="특정 work_id만")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sleep", type=float, default=1.5, help="건당 대기(인스타 레이트리밋 회피)")
    a = ap.parse_args()

    db = _db_path()
    print("DB:", db, "| dry-run" if a.dry_run else "| 실제 반영")
    con = sqlite3.connect(db)
    cur = con.cursor()
    cache = {}
    fixed_basket = fixed_work = 0

    # ── 1) 작업 handoff 복사본 ────────────────────────────────────────
    if a.work:
        cur.execute("SELECT work_id, customer_id, state_json FROM produce_works WHERE work_id=?",
                    (a.work,))
    else:
        cur.execute("SELECT work_id, customer_id, state_json FROM produce_works "
                    "WHERE updated_at >= date('now', ?)", ("-%d day" % a.days,))
    rows = cur.fetchall()
    print("작업 %d개 검사" % len(rows))
    for work_id, cid, sj in rows:
        try:
            st = json.loads(sj or "{}")
        except Exception:  # noqa: BLE001 — 깨진 state는 건드리지 않는다
            continue
        handoff = st.get("handoff")
        if not isinstance(handoff, list) or not handoff:
            continue
        holes = [x for x in handoff
                 if isinstance(x, dict) and x.get("url") and not (x.get("thumbnail") or "")]
        if not holes:
            continue
        print("  work=%s cid=%s 빈것 %d/%d" % (work_id, cid, len(holes), len(handoff)))
        changed = False
        for item in holes:
            meta = _probe(item["url"], cache)
            time.sleep(a.sleep)
            if not meta.get("thumbnail"):
                print("     실패 %s" % item["url"][-16:])
                continue
            item["thumbnail"] = meta["thumbnail"]
            if not (item.get("name") or "") and meta.get("title"):
                item["name"] = meta["title"]
            changed = True
            print("     OK   %s -> %s" % (item["url"][-16:], meta["thumbnail"][:48]))
        if changed and not a.dry_run:
            cur.execute("UPDATE produce_works SET state_json=? WHERE work_id=?",
                        (json.dumps(st, ensure_ascii=False), work_id))
            con.commit()
        fixed_work += 1 if changed else 0

    # ── 2) 즐겨찾기 바구니 ────────────────────────────────────────────
    cur.execute("SELECT shortcode, customer_id, url FROM mix_basket "
                "WHERE (thumbnail IS NULL OR thumbnail='') AND url<>'' "
                "AND added_at >= date('now', ?)", ("-%d day" % a.days,))
    brows = cur.fetchall()
    print("바구니 빈 항목 %d건" % len(brows))
    for sc, cid, url in brows:
        meta = _probe(url, cache)
        if url not in cache or not meta.get("thumbnail"):
            time.sleep(a.sleep)
        if not meta.get("thumbnail"):
            continue
        if not a.dry_run:
            cur.execute("UPDATE mix_basket SET thumbnail=?, name=COALESCE(NULLIF(name,''),?) "
                        "WHERE shortcode=? AND customer_id=?",
                        (meta["thumbnail"], meta.get("title") or "", sc, cid))
            con.commit()
        fixed_basket += 1
        print("  OK %s" % sc[-14:])

    con.close()
    print("\n결과: 작업 %d개 · 바구니 %d건 복구%s"
          % (fixed_work, fixed_basket, "(dry-run, 반영 안 함)" if a.dry_run else ""))


if __name__ == "__main__":
    main()
