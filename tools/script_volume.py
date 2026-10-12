# -*- coding: utf-8 -*-
"""대본 생성이 하루에 몇 번 도나 — 필자(모델) 교체 비용을 어림하려고 센다 (2026-09-21).
서버에서(읽기 전용, mode=ro, 집계 숫자만):  python3 /home/ubuntu/patchcheck/script_volume.py [--days 14]"""
import argparse
import datetime
import sqlite3

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
ap = argparse.ArgumentParser()
ap.add_argument("--days", type=int, default=14)
a = ap.parse_args()
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
since = (datetime.datetime.utcnow() - datetime.timedelta(days=a.days)).strftime("%Y-%m-%d")
print("== op별 합계(최근 %d일, trial 제외)" % a.days)
for op, n, days, cust in con.execute(
        "SELECT op, SUM(count), COUNT(DISTINCT day), COUNT(DISTINCT customer_id) FROM usage "
        "WHERE day >= ? AND day != 'trial' GROUP BY op ORDER BY 2 DESC", (since,)):
    print("  %-14s 합 %5d · %2d일 · 고객 %3d명 · 하루 평균 %.1f" % (op, n, days, cust, n / max(1, days)))
print("== script 일별(전체 / 최다 고객 1명)")
for day, n, mx, cust in con.execute(
        "SELECT day, SUM(count), MAX(count), COUNT(DISTINCT customer_id) FROM usage "
        "WHERE op='script' AND day >= ? AND day != 'trial' GROUP BY day ORDER BY day", (since,)):
    print("  %s  %4d회 · 고객 %3d명 · 1인 최다 %3d" % (day, n, cust, mx))
print("== script 상위 계정(최근 %d일) — 전역 합계용 행이 섞였나 본다" % a.days)
for cid, n in con.execute("SELECT customer_id, SUM(count) FROM usage WHERE op='script' AND day >= ? AND day != 'trial' "
                          "GROUP BY customer_id ORDER BY 2 DESC LIMIT 6", (since,)):
    print("  cid %-6s %6d회" % (cid, n))
