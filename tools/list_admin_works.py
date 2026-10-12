# -*- coding: utf-8 -*-
"""관리자(cid 0) 최근 작업 목록 — 격리 점검에 쓸 재료를 고르려고 본다(읽기 전용, mode=ro).
서버: python3 /home/ubuntu/patchcheck/list_admin_works.py [--n 25]"""
import argparse
import json
import sqlite3

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=25)
a = ap.parse_args()
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
for wid, title, jid, step, upd, sj in con.execute(
        "SELECT work_id, title, job_id, step, updated_at, state_json FROM produce_works "
        "WHERE customer_id=0 AND job_id IS NOT NULL AND job_id!='' ORDER BY updated_at DESC LIMIT ?", (a.n,)):
    try:
        n_src = sum(1 for h in (json.loads(sj or "{}").get("handoff") or []) if h.get("useFootage"))
    except Exception:      # noqa: BLE001
        n_src = -1
    print("%s  %s  step%-2s 영상%-2d %s" % (wid, (upd or "")[:16], step, n_src, (title or "")[:40]))
