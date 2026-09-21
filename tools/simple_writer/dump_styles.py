# -*- coding: utf-8 -*-
"""[서버용] 스타일(스파인)이 가진 것을 JSON으로 — 훅 틀·칸 순서·말투·뼈대로 쓸 히트작 원문 (2026-09-21).
읽기 전용(mode=ro). 단순 필자 하네스의 '고객이 고른 스타일' 경로 입력.
    python3 /home/ubuntu/patchcheck/dump_styles.py --styles 61,59,52,53 [--per 3]   /  --list 로 승인 스타일 목록"""
import argparse
import json
import sqlite3
import sys

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
ap = argparse.ArgumentParser()
ap.add_argument("--styles", default="")
ap.add_argument("--per", type=int, default=3)
ap.add_argument("--list", action="store_true")
a = ap.parse_args()
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
con.row_factory = sqlite3.Row


def hits_for(sid, n):
    rows = con.execute("SELECT id, full_text, perf_json, is_winner, product_category FROM pattern_source "
                       "WHERE spine_id=? AND LENGTH(full_text) BETWEEN 120 AND 900 ORDER BY is_winner DESC, id DESC LIMIT ?",
                       (sid, n)).fetchall()
    return [{"id": r["id"], "text": (r["full_text"] or "").strip(), "winner": r["is_winner"], "cat": r["product_category"]} for r in rows]


if a.list:
    for r in con.execute("SELECT id, name, templates_json FROM spine WHERE status='approved' ORDER BY id"):
        n_hit = con.execute("SELECT COUNT(*) FROM pattern_source WHERE spine_id=? AND LENGTH(full_text)>=120", (r["id"],)).fetchone()[0]
        try:
            t = json.loads(r["templates_json"] or "{}") or {}
        except Exception:      # noqa: BLE001
            t = {}
        o = t.get("_origin") if isinstance(t, dict) else None
        n_hook = len(t.get("hook") or []) if isinstance(t, dict) and isinstance(t.get("hook"), list) else 0
        print("%4d  훅틀 %2d · 연결된 히트 전사 %3d · 원문내장 %s  %s" % (r["id"], n_hook, n_hit, "O" if o else "-", r["name"]))
    sys.exit(0)
out = []
for sid in [int(x) for x in a.styles.split(",") if x.strip().isdigit()]:
    r = con.execute("SELECT id, name, beat_roles_json, beat_chain_json, templates_json FROM spine WHERE id=?", (sid,)).fetchone()
    if not r:
        continue
    try:
        t = json.loads(r["templates_json"] or "{}") or {}
    except Exception:      # noqa: BLE001
        t = {}
    o = t.get("_origin") if isinstance(t, dict) else None
    origin_text = "\n".join(str(c.get("text") or "") for c in (o.get("cells") or [])) if isinstance(o, dict) else ""
    out.append({"id": sid, "name": r["name"], "roles": json.loads(r["beat_roles_json"] or "[]"),
                "hooks": [h for h in (t.get("hook") or []) if isinstance(h, str)] if isinstance(t, dict) else [],
                "templates": {k: v for k, v in t.items() if k != "_origin" and isinstance(v, list)} if isinstance(t, dict) else {},
                "origin": origin_text, "hits": hits_for(sid, a.per)})
sys.stdout.write("@@JSON@@" + json.dumps(out, ensure_ascii=False))
