# -*- coding: utf-8 -*-
"""finish 로그(.tracks/_finish_logs/*.log)를 단계별 시간으로 쪼개 어디서 시간이 새는지 잰다(2026-10-15).

    py tools/finish_time_audit.py            # 전체 합계·단계별 분·낭비 후보
    py tools/finish_time_audit.py --days 3   # 최근 N일 로그만

단계: 시험(pytest 게이트) · 시험 자원 대기 · 영상 관문 순번 대기 · 영상 관문 실행 · 재시험 횟수.
"""
import re
import sys
import time
from collections import Counter
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / ".tracks" / "_finish_logs"
if not LOG_DIR.exists():                                   # 트랙 폴더에서 돌 때 — main 폴더의 로그
    LOG_DIR = Path(__file__).resolve().parents[3] / ".tracks" / "_finish_logs"
TS = re.compile(r"^(\d\d):(\d\d):(\d\d) (.*)")


def _sec(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


def parse(path):
    """로그 한 개 → 단계별 초. 자정을 넘기면 +24h."""
    st = {"test": 0, "res_wait": 0, "vg_wait": 0, "vg_run": 0, "vg_reuse": 0, "reruns": 0,
          "dup_ctrl": 0, "total": 0, "result": "?", "rerun_code": 0, "rerun_files": []}
    lines = []
    last, day = None, 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS.match(raw)
        if not m:
            if "병합 완료" in raw or "✅ main" in raw:
                st["result"] = "ok"
            elif raw.startswith("중단"):
                st["result"] = "fail"
            continue
        t = _sec(*m.groups()[:3])
        if last is not None and t < last - 3600:
            day += 86400
        last = t
        lines.append((t + day, m.group(4)))
    if not lines:
        return None
    st["total"] = lines[-1][0] - lines[0][0]
    mark = {}
    for t, msg in lines:
        if "[대기] 시험 자원" in msg and "res" not in mark:
            mark["res"] = t
        elif msg.startswith("시험 자원:") and "res" in mark:
            st["res_wait"] += t - mark.pop("res")
        if "게이트 실행 중" in msg:
            mark["test"] = t
        elif ("게이트 통과" in msg or "게이트 실패" in msg) and "test" in mark:
            st["test"] += t - mark.pop("test")
        if "다른 트랙의 영상 관문" in msg and "vgw" not in mark:
            mark["vgw"] = t
        if msg.startswith("영상 관문: 실행"):
            if "vgw" in mark:
                st["vg_wait"] += t - mark.pop("vgw")
            mark["vg"] = t
        elif ("영상 관문 통과" in msg or "영상 관문 실패" in msg) and "vg" in mark:
            d = t - mark.pop("vg")
            if "다시 안 돌렸다" in msg:
                st["vg_reuse"] += 1
            st["vg_run"] += d
        if "최신 main 위에서 다시 잰다" in msg:
            st["reruns"] += 1
        m2 = re.search(r"끼어든 main 커밋에 코드가 있다\((\d+)개, 예: ([^)]+)\)", msg)
        if m2:
            st["rerun_code"] += 1
            st["rerun_files"].append(m2.group(2).strip())
        if "선점 충돌" in msg:
            st["dup_ctrl"] += 1
    return st


def main():
    days = None
    if "--days" in sys.argv:
        days = float(sys.argv[sys.argv.index("--days") + 1])
    logs = sorted(LOG_DIR.glob("*.log"))
    if days:
        cut = time.time() - days * 86400
        logs = [p for p in logs if p.stat().st_mtime >= cut]
    rows = [(p, parse(p)) for p in logs]
    rows = [(p, s) for p, s in rows if s]
    n = len(rows)
    tot = Counter()
    for _, s in rows:
        for k in ("test", "res_wait", "vg_wait", "vg_run", "total", "reruns", "vg_reuse"):
            tot[k] += s[k]
    mn = lambda x: "%.0f분" % (x / 60)
    print("finish 로그 %d건 (%s)" % (n, LOG_DIR))
    print("  전체 걸린 시간 합  %s  (건당 평균 %s)" % (mn(tot["total"]), mn(tot["total"] / max(n, 1))))
    print("  ├ 시험(pytest)     %s" % mn(tot["test"]))
    print("  ├ 시험 자원 대기   %s" % mn(tot["res_wait"]))
    print("  ├ 영상 관문 대기   %s" % mn(tot["vg_wait"]))
    print("  └ 영상 관문 실행   %s  (재사용 %d회)" % (mn(tot["vg_run"]), tot["vg_reuse"]))
    rr = [s for _, s in rows if s["reruns"]]
    print("  재시험(main 끼어듦) %d회 · 그런 finish %d건" % (tot["reruns"], len(rr)))
    # 재시험으로 다시 돈 시험 시간 = 재시험이 있는 로그의 시험 시간 중 첫 회를 뺀 몫(근사: 시험시간 × reruns/(reruns+1))
    waste = sum(s["test"] * s["reruns"] / (s["reruns"] + 1) for s in rr)
    print("  └ 재시험으로 다시 돈 시험 시간(근사)  %s" % mn(waste))
    fc = Counter(f for _, s in rows for f in s["rerun_files"])
    print("  재시험을 부른 끼어든 파일 상위:", ", ".join("%s %d" % kv for kv in fc.most_common(5)))
    res = Counter(s["result"] for _, s in rows)
    print("  결과:", dict(res))
    slow = sorted(rows, key=lambda r: -r[1]["total"])[:5]
    print("  가장 오래 걸린 5건:")
    for p, s in slow:
        print("    %s  %s (시험 %s · 자원대기 %s · 영상대기 %s · 재시험 %d)" % (
            p.stem, mn(s["total"]), mn(s["test"]), mn(s["res_wait"]), mn(s["vg_wait"]), s["reruns"]))


if __name__ == "__main__":
    main()
