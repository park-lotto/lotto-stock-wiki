# -*- coding: utf-8 -*-
"""씨앗 컷 자동 배치 유출 검사(관제 138) — 라이브 작업의 편집 계획에서 센다.

됐다의 기준: 씨앗 표식(auto_exclude)이 달린 작업의 자동 컷(대표·대안)에 씨앗 조각 0개.
  수리 전 실측(2026-10-06, 최근 6일): 82건 중 36건 유출.

세는 법
  · 대안 컷(alternates)의 씨앗 조각 = 전부 자동(사람은 편성·교체로만 넣는다 — scene_override/manual_cuts/primary)
  · 대표 컷(primary)의 씨앗 조각 = fit 값이 있으면 자동. fit 이 비었으면 사람이 [교체]로 넣었을 수 있어 따로 센다
  · 스토리보드에서 사람이 고른 줄(pinned)은 세지 않는다

쓰는 법
  py tools/seed_leak_check.py --ssh                 # 로컬에서: 서버로 보내 실행(최근 24시간)
  py tools/seed_leak_check.py --ssh --since 2026-10-07T04:00    # 배포 뒤 만든 작업만(UTC)
  python3 tools/seed_leak_check.py --hours 72       # 서버에서 직접
끝 코드: 자동 유출 0 → 0, 있으면 1, 검사 대상 0건 → 2(판정 불가)
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys

SERVER = "ubuntu@shoppingshorts.duckdns.org"
REPO = "/home/ubuntu/lotto-stock-wiki"
KEY = r"C:\Users\CH\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem"


def scan(db, since=None, hours=24.0):
    c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    c.row_factory = sqlite3.Row
    if since:
        rows = c.execute("select job_id, created_at, status, script_structure_json, extract_json, edit_plan_json "
                         "from mix_jobs where created_at >= ? order by created_at", (since,)).fetchall()
    else:
        rows = c.execute("select job_id, created_at, status, script_structure_json, extract_json, edit_plan_json "
                         "from mix_jobs where created_at >= datetime('now', ?) order by created_at",
                         ("-%d minutes" % int(float(hours) * 60),)).fetchall()
    out = {"jobs": 0, "leak_jobs": 0, "auto_leaks": 0, "maybe_human": 0, "detail": []}
    for r in rows:
        try:
            ss = json.loads(r["script_structure_json"] or "{}")
            ex = json.loads(r["extract_json"] or "{}")
            plan = json.loads(r["edit_plan_json"] or "{}")
        except Exception:      # noqa: BLE001 — 깨진 행은 검사 대상이 아니다
            continue
        if not isinstance(ss, dict) or not ss.get("no_auto_idx") or not isinstance(plan, dict):
            continue
        seed = {g.get("seg_id") for s in (ex or {}).values() if isinstance(s, dict) and s.get("auto_exclude")
                for g in (s.get("segments") or [])}
        beats = plan.get("beats") or []
        if not seed or not beats:
            continue
        out["jobs"] += 1
        auto, maybe = [], []
        for b in beats:
            if b.get("pinned"):
                continue
            p = b.get("primary") or {}
            if p.get("seg_id") in seed:
                (auto if b.get("fit") is not None else maybe).append("칸%s 대표 %s(%s)" % (
                    b.get("beat_idx"), p.get("seg_id"), b.get("fit_evidence")))
            for a in b.get("alternates") or []:
                if isinstance(a, dict) and a.get("seg_id") in seed:
                    auto.append("칸%s 대안 %s" % (b.get("beat_idx"), a.get("seg_id")))
        out["auto_leaks"] += len(auto)
        out["maybe_human"] += len(maybe)
        if auto:
            out["leak_jobs"] += 1
            out["detail"].append("%s %s %s generator=%s: %s" % (
                r["job_id"], r["created_at"][:16], r["status"], plan.get("generator"), " / ".join(auto[:6])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--since", default="", help="이 시각(UTC, 예 2026-10-07T04:00) 뒤에 만든 작업만")
    ap.add_argument("--db", default="shopping_shorts/data/reference.db")
    ap.add_argument("--ssh", action="store_true", help="서버로 보내 실행")
    a = ap.parse_args()
    if a.ssh:
        args = "--hours %s" % a.hours + (" --since %s" % a.since if a.since else "")
        src = open(os.path.abspath(__file__), "rb").read()
        r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", "-i", KEY, SERVER,
                            "cd %s && timeout 120 python3 - %s" % (REPO, args)], input=src)
        return r.returncode
    res = scan(a.db, since=a.since or None, hours=a.hours)
    for d in res["detail"]:
        print("  유출 " + d)
    print("씨앗 표식 작업 %d건 · 자동 유출 작업 %d건 · 자동 유출 조각 %d개 · 사람이 바꿨을 수 있는 대표 컷 %d개"
          % (res["jobs"], res["leak_jobs"], res["auto_leaks"], res["maybe_human"]))
    if not res["jobs"]:
        print("판정 불가 — 검사 대상 작업이 없다")
        return 2
    return 1 if res["auto_leaks"] else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:      # noqa: BLE001
        pass
    sys.exit(main())
