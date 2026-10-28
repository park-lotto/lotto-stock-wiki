# -*- coding: utf-8 -*-
"""finish 단계별 시간 집계(2026-10-03 사장님 "비효율적이거나 오래 걸리는 것들 잘 체크해야 한다", 카드 089).

.tracks/_finish_logs/<트랙>_<YYYYmmdd_HHMMSS>.log (줄마다 시각) 를 읽어 트랙별로
  줄 밖 시험 · 영상 관문 · 줄(락) 대기 · 재시도 수 · 전체 를 분 단위로 보여준다.
시각이 없는 옛 로그는 시작(파일 이름)~끝(.rc 시각)만 잰다.

    py tools/finish_report.py            # 최근 20개
    py tools/finish_report.py --n 50
"""
import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
TS = re.compile(r"^(\d\d):(\d\d):(\d\d) (.*)$")

# 단계 시작 표식 → 이름 (먼저 나온 표식부터 다음 표식까지가 그 단계)
MARKS = [
    ("게이트 실행 중", "시험"),
    ("코드 없는 병합", "시험"),
    ("영상 관문: 실행", "영상관문"),
    ("[대기] 다른 트랙의 영상 관문", "영상락대기"),
    ("검사 끝 — 줄에 선다", "줄대기"),
    ("[대기] 다른 트랙이 finish 게이트", "줄대기"),
    ("병합 완료", "끝"),
    ("중단:", "끝"),
    ("다시 잰다", "재시도"),
    ("다시 시도", "재시도"),
]


LOG_NAME = re.compile(r"(.+)_(\d{8}_\d{6})\.log$")


def parse(path):
    """finish 로그 한 개 → 행. 이름이 <트랙>_<YYYYmmdd_HHMMSS>.log 가 아니면(sched_test.log 등) None(관제 157)."""
    mt = LOG_NAME.match(path.name)
    if not mt:
        return None
    name, stamp = mt.groups()
    start = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
    rc = path.with_suffix(".rc")
    end = datetime.fromtimestamp(rc.stat().st_mtime) if rc.exists() else None
    events, day, last = [], start.date(), None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS.match(line)
        if not m:
            continue
        t = datetime.combine(day, datetime.min.time()).replace(hour=int(m.group(1)), minute=int(m.group(2)),
                                                               second=int(m.group(3)))
        if last and t < last - timedelta(hours=1):          # 자정 넘김
            day += timedelta(days=1)
            t += timedelta(days=1)
        last = t
        for k, v in MARKS:
            if k in m.group(4):
                events.append((t, v, m.group(4)))
                break
    phases, retries = {}, 0
    pushed_at = next((t for t, v, _ in events if v == "끝" and "병합 완료" in _), None)
    for i, (t, v, _) in enumerate(events):
        if v == "재시도":
            retries += 1
            continue
        if v == "끝":
            continue
        nxt = next((e[0] for e in events[i + 1:]), end or last or t)
        phases[v] = phases.get(v, 0) + (nxt - t).total_seconds()
    result = "진행 중"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "병합 완료" in text:
        result = "병합"
    elif "중단:" in text or "❌" in text:
        result = "막힘"
    grade = "급행" if "등급: 급행" in text else ("보통" if "등급: 보통" in text else "-")
    holds = text.count("[급행 보류] 급행 finish")
    total = ((end or (datetime.now() if result == "진행 중" else (last or start))) - start).total_seconds()
    return {"트랙": name, "시작": start.strftime("%m-%d %H:%M"), "전체": total, "결과": result, "재시도": retries, "등급": grade, "보류": holds,
            "push분": ((pushed_at - start).total_seconds() / 60) if pushed_at else None,
            "시각있음": bool(events), **phases}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--dir", default=None)
    a = ap.parse_args(argv)
    if a.dir:
        d = Path(a.dir)
    else:
        sys.path.insert(0, str(HERE))
        import track
        d = track.tracks_dir(track.BASE) / "_finish_logs"
    logs = sorted((p for p in d.glob("*_*.log") if LOG_NAME.match(p.name)), key=lambda p: p.name[-19:],
                  reverse=True)[: a.n]
    rows = [r for r in (parse(p) for p in logs) if r is not None]
    cols = ["시험", "영상관문", "영상락대기", "줄대기"]
    m = lambda s: ("%5.1f" % (s / 60)) if s else "    -"   # noqa: E731
    print("%-14s %-11s %4s %6s %7s  %s  %4s  %4s  %s" % ("트랙", "시작", "등급", "전체분", "push분",
                                                      "  ".join("%5s" % c[:5] for c in cols), "재시도", "보류", "결과"))
    for r in rows:
        print("%-14s %-11s %4s %6.1f %7s  %s  %4d  %4d  %s%s" % (
            r["트랙"][:14], r["시작"], r["등급"], r["전체"] / 60,
            ("%7.1f" % r["push분"]) if r["push분"] is not None else "      -",
            "  ".join(m(r.get(c, 0)) for c in cols), r["재시도"], r["보류"], r["결과"],
                                               "" if r["시각있음"] else " (옛 로그: 단계 시각 없음)"))
    timed = [r for r in rows if r["시각있음"] and r["결과"] == "병합"]
    if timed:
        print("\n병합된 %d건 평균(분): " % len(timed) + " · ".join(
            "%s %.1f" % (c, sum(r.get(c, 0) for r in timed) / len(timed) / 60) for c in cols + ["전체"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
