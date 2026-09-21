# -*- coding: utf-8 -*-
"""훅 틀이 몇 개나 있고 얼마나 긴가 — 단순 필자에 '훅 유형 하나 고르기'를 붙이면 프롬프트가 얼마나 느나 (2026-09-21).
서버(읽기 전용 mode=ro):  python3 /home/ubuntu/patchcheck/hook_census.py"""
import json
import sqlite3
import statistics as st

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
tpl_hooks, origin_hooks, per_spine = [], [], []
n_spine = n_tpl = n_origin = 0
for sid, name, status, tj in con.execute("SELECT id, name, status, templates_json FROM spine WHERE status='approved'"):
    n_spine += 1
    try:
        t = json.loads(tj or "{}") or {}
    except Exception:      # noqa: BLE001
        continue
    o = t.get("_origin") if isinstance(t, dict) else None
    if isinstance(o, dict) and o.get("cells"):
        n_origin += 1
        h = (o.get("hook_tpl") or (o["cells"][0].get("text") if o["cells"] else "") or "").strip()
        if h:
            origin_hooks.append(h)
        continue
    hs = []
    for k in ("hook", "title", "훅"):
        v = t.get(k) if isinstance(t, dict) else None
        if isinstance(v, list):
            hs += [x for x in v if isinstance(x, str) and x.strip()]
    if hs:
        n_tpl += 1
        per_spine.append(len(hs))
        tpl_hooks += hs
print("승인된 스타일(스파인) %d개 = 틀형 %d개 + 원문형 %d개" % (n_spine, n_tpl, n_origin))
if tpl_hooks:
    print("틀형 훅 틀: 모두 %d개 · 스타일당 중앙값 %d개 · 길이 중앙값 %d자(최대 %d자)" % (
        len(tpl_hooks), st.median(per_spine), st.median(len(h) for h in tpl_hooks), max(len(h) for h in tpl_hooks)))
    print("  예:", " / ".join(tpl_hooks[:6]))
if origin_hooks:
    print("원문형 훅: %d개 · 길이 중앙값 %d자" % (len(origin_hooks), st.median(len(h) for h in origin_hooks)))
    print("  예:", " / ".join(origin_hooks[:5]))
