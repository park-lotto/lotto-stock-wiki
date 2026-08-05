# -*- coding: utf-8 -*-
"""부품은행 표기 변형 통합 (대본퀄 v6, 2026-08-05).

'~더라고요/하더라고요/~더라구요' 처럼 표기만 다른 부품이 별도 행으로 쌓여
어미가 과포화됐다(ending 버킷 실측: 더라고요 계열 5행 203회). 강화된
`_normalize_canonical`(물결 접두 제거·더라구→더라고·ending 축약) 기준으로
같은 canonical이 되는 행들을 묶어 1행으로 통합한다.

- 대표행 = freq 최대(동률이면 approved 우선) / freq 합산·source_ids 합집합
- 나머지 행은 **삭제하지 않고 status='merged'** (approved 필터에서 빠져 프롬프트
  주입만 제외 — 필요하면 status 되돌려 복구 가능)
- 기본 dry-run. 실제 반영은 --apply.

사용: python3 -m shopping_shorts.scripts.merge_pattern_variants [--apply] [--bucket ending]
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

from shopping_shorts.store import Store, _normalize_canonical
from shopping_shorts import config


def merge(store, bucket=None, apply=False, out=print):
    with store._conn() as c:
        conds, args = ["is_negative=0"], []
        if bucket:
            conds.append("bucket=?")
            args.append(bucket)
        rows = c.execute(
            "SELECT id, bucket, text, canonical, freq, status, source_ids_json "
            f"FROM pattern_item WHERE {' AND '.join(conds)}", args).fetchall()

    groups = defaultdict(list)
    for r in rows:
        rid, bkt, text, canon, freq, status, sids = r
        key = (bkt, _normalize_canonical(text, bkt))
        groups[key].append({"id": rid, "text": text, "freq": freq or 0,
                            "status": status, "sids": sids})

    merged_total = 0
    now = datetime.now(timezone.utc).isoformat()
    for (bkt, canon), items in sorted(groups.items()):
        if len(items) < 2:
            continue
        # 대표행: freq 최대, 동률이면 approved 우선
        items.sort(key=lambda x: (x["freq"], x["status"] == "approved"), reverse=True)
        keeper, rest = items[0], items[1:]
        total_freq = sum(x["freq"] for x in items)
        sids = []
        for x in items:
            try:
                for s in json.loads(x["sids"] or "[]"):
                    if s not in sids:
                        sids.append(s)
            except Exception:
                pass
        out(f"[{bkt}] '{canon}' ← {len(items)}행 (freq합 {total_freq}) "
            f"대표 id={keeper['id']} '{keeper['text']}' / 접힘: "
            + ", ".join(f"id={x['id']} '{x['text']}'({x['freq']})" for x in rest))
        merged_total += len(rest)
        if apply:
            with store._conn() as c:
                c.execute(
                    "UPDATE pattern_item SET canonical=?, freq=?, source_ids_json=?, "
                    "updated_at=? WHERE id=?",
                    (canon, total_freq, json.dumps(sids, ensure_ascii=False), now,
                     keeper["id"]))
                for x in rest:
                    c.execute(
                        "UPDATE pattern_item SET status='merged', note=?, updated_at=? "
                        "WHERE id=?",
                        (f"merged into id={keeper['id']} ({canon})", now, x["id"]))
    out(f"\n{'[적용]' if apply else '[dry-run]'} 접힌 행 {merged_total}개")
    return merged_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--bucket", default=None)
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    store = Store(a.db or config.DB_PATH)
    merge(store, bucket=a.bucket, apply=a.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
