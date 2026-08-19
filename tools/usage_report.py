"""Gemini 사용량 통계 — "제작소 1편에 얼마 나가나"를 실측으로 답한다.

    py tools/usage_report.py                 # 전체 요약(4종 다)
    py tools/usage_report.py --days 7        # 최근 7일만
    py tools/usage_report.py --op            # 기능별만
    py tools/usage_report.py --jobs          # 영상 1편당만
    py tools/usage_report.py --customers     # 사용자별만
    py tools/usage_report.py --daily         # 일자별만
    py tools/usage_report.py --db <경로>     # 서버 DB를 직접 지정

기록은 shopping_shorts/usage_meter.py 가 gemini_usage 테이블에 쌓는다.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE / "shopping_shorts" / "data" / "reference.db"


def _fmt_krw(v):
    return "-" if v is None else f"{v:,.1f}원"


def _table(rows, headers, aligns=None):
    if not rows:
        return "   (기록 없음)"
    cols = len(headers)
    w = [len(str(h)) for h in headers]
    for r in rows:
        for i in range(cols):
            w[i] = max(w[i], len(str(r[i])))
    aligns = aligns or ["<"] * cols
    out = ["  " + "  ".join(f"{headers[i]:{aligns[i]}{w[i]}}" for i in range(cols)),
           "  " + "  ".join("-" * w[i] for i in range(cols))]
    for r in rows:
        out.append("  " + "  ".join(f"{str(r[i]):{aligns[i]}{w[i]}}" for i in range(cols)))
    return "\n".join(out)


def _where(days):
    if not days:
        return "", ()
    return " WHERE day >= date('now', ?) ", (f"-{int(days)} day",)


def report(db, days=None, want=None):
    if not Path(db).exists():
        print(f"DB 없음: {db}")
        return 1
    conn = sqlite3.connect(str(db))
    try:
        has = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='gemini_usage'").fetchone()
        if not has:
            print("gemini_usage 테이블이 아직 없습니다 — 계측 후 첫 호출이 일어나면 생깁니다.")
            return 0

        w, p = _where(days)
        tot = conn.execute(
            f"SELECT COUNT(*), COALESCE(SUM(in_tokens),0), COALESCE(SUM(out_tokens),0),"
            f" COALESCE(SUM(krw),0) FROM gemini_usage{w}", p).fetchone()
        scope = f"최근 {days}일" if days else "전체"
        print(f"\n=== Gemini 사용량 ({scope}) ===")
        print(f"  호출 {tot[0]:,}건 · 입력 {tot[1]:,} · 출력 {tot[2]:,} 토큰 · 합계 {_fmt_krw(tot[3])}")
        if tot[0] == 0:
            print("\n  아직 기록이 없습니다. 제작소/태거를 한 번 돌리면 쌓입니다.")
            return 0

        want = want or {"jobs", "op", "customers", "daily"}

        if "jobs" in want:
            print("\n[영상 1편당 총비용]")
            rows = conn.execute(
                f"SELECT job_id, COUNT(*), SUM(in_tokens+out_tokens), ROUND(SUM(krw),2)"
                f" FROM gemini_usage{w}{'AND' if w else ' WHERE'} job_id IS NOT NULL"
                f" GROUP BY job_id ORDER BY SUM(krw) DESC LIMIT 15", p).fetchall()
            print(_table([(r[0], f"{r[1]:,}", f"{r[2]:,}", _fmt_krw(r[3])) for r in rows],
                         ["job_id", "콜", "토큰", "비용"], ["<", ">", ">", ">"]))
            avg = conn.execute(
                f"SELECT ROUND(AVG(c),2) FROM (SELECT SUM(krw) c FROM gemini_usage{w}"
                f"{'AND' if w else ' WHERE'} job_id IS NOT NULL GROUP BY job_id)", p).fetchone()[0]
            if avg is not None:
                print(f"\n  ★ 영상 1편 평균: {_fmt_krw(avg)}"
                      f"   → $300(44만원)이면 약 {int(440000/avg):,}편")

        if "op" in want:
            print("\n[기능별 비용]")
            rows = conn.execute(
                f"SELECT COALESCE(op,'(미분류)'), COUNT(*), ROUND(AVG(krw),3),"
                f" ROUND(SUM(krw),2) FROM gemini_usage{w}"
                f" GROUP BY op ORDER BY SUM(krw) DESC", p).fetchall()
            print(_table([(r[0], f"{r[1]:,}", f"{r[2]}원", _fmt_krw(r[3])) for r in rows],
                         ["기능", "콜", "건당평균", "합계"], ["<", ">", ">", ">"]))

        if "customers" in want:
            print("\n[사용자별 누적]")
            rows = conn.execute(
                f"SELECT COALESCE(customer_id,'(미상)'), COUNT(*),"
                f" COUNT(DISTINCT job_id), ROUND(SUM(krw),2) FROM gemini_usage{w}"
                f" GROUP BY customer_id ORDER BY SUM(krw) DESC LIMIT 20", p).fetchall()
            print(_table([(r[0], f"{r[1]:,}", f"{r[2]:,}", _fmt_krw(r[3])) for r in rows],
                         ["사용자", "콜", "영상", "누적"], ["<", ">", ">", ">"]))

        if "daily" in want:
            print("\n[일자별 추이]")
            rows = conn.execute(
                f"SELECT day, COUNT(*), ROUND(SUM(krw),2) FROM gemini_usage{w}"
                f" GROUP BY day ORDER BY day DESC LIMIT 30", p).fetchall()
            mx = max((r[2] or 0) for r in rows) or 1
            body = [(r[0], f"{r[1]:,}", _fmt_krw(r[2]),
                     "█" * max(1, int((r[2] or 0) / mx * 28))) for r in rows]
            print(_table(body, ["날짜", "콜", "비용", ""], ["<", ">", ">", "<"]))

        print("\n[모델별]")
        rows = conn.execute(
            f"SELECT model, COUNT(*), ROUND(SUM(krw),2) FROM gemini_usage{w}"
            f" GROUP BY model ORDER BY SUM(krw) DESC", p).fetchall()
        print(_table([(r[0], f"{r[1]:,}", _fmt_krw(r[2])) for r in rows],
                     ["모델", "콜", "합계"], ["<", ">", ">"]))
        print()
        return 0
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("USAGE_DB", str(DEFAULT_DB)))
    ap.add_argument("--days", type=int, default=None)
    for f in ("jobs", "op", "customers", "daily"):
        ap.add_argument(f"--{f}", action="store_true")
    a = ap.parse_args()
    want = {f for f in ("jobs", "op", "customers", "daily") if getattr(a, f)}
    return report(a.db, a.days, want or None)


if __name__ == "__main__":
    sys.exit(main())
