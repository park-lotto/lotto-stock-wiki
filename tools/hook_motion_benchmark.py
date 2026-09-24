# -*- coding: utf-8 -*-
"""터진 영상의 **훅 첫 3초가 화면으로 어떻게 움직이는가**를 픽셀로 잰다 (2026-09-24).

왜 있나: 장면 태깅(scene_desc)은 "~하는 모습"이라는 정형 문구라 카메라 문법이 안 나온다
(hook_benchmark.py 실측: 제일 흔한 말 '모습'이 터진 61% 대조 57%로 차이 없음). 카메라가
어떻게 움직이는지는 글이 아니라 **영상을 봐야** 안다. 여기서는 서버에 이미 받아둔 원본만
쓴다 — 인스타는 익명 내려받기가 막혀 있어 새로 받으려면 계정·프록시를 태워야 한다.

    python3 tools/hook_motion_benchmark.py [--db 경로] [--top 114] [--seconds 3]

출력: 터진 군과 대조군의 첫 3초 움직임 세기·앞쏠림·컷 전환 수 비교.
"""
import argparse
import glob
import json
import os
import subprocess

W, H, FPS = 64, 114, 10


def frames(path, seconds):
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-t", str(seconds), "-i", str(path),
         "-vf", f"fps={FPS},scale={W}:{H},format=gray", "-f", "rawvideo", "-"],
        capture_output=True, stdin=subprocess.DEVNULL).stdout
    n = W * H
    return [out[i:i + n] for i in range(0, len(out) - n + 1, n)]


def profile(path, seconds):
    """(평균 움직임, 첫1초 비중%, 컷처럼 튄 횟수) — 못 읽으면 None."""
    fs = frames(path, seconds)
    if len(fs) < 8:
        return None
    diffs = []
    for i in range(1, len(fs)):
        a, b = fs[i - 1], fs[i]
        d = sum(abs(a[j] - b[j]) for j in range(0, len(a), 7)) / (len(a) / 7)
        diffs.append(d)
    total = sum(diffs) or 1e-9
    first1 = sum(diffs[:FPS]) / total * 100
    srt = sorted(diffs)
    med = srt[len(srt) // 2] or 1e-9
    spikes = sum(1 for d in diffs if d > med * 3)
    return (round(total / len(diffs), 2), round(first1, 1), spikes)


def files_for(db, limit, order):
    """조회수 순으로 뽑아 서버에 실제로 파일이 있는 것만 {shortcode: 경로}."""
    import sqlite3
    c = sqlite3.connect(db)
    q = ("select a.shortcode, a.views from script_extracts e join channel_archive a "
         "on a.shortcode = e.shortcode where a.views > 0 order by a.views %s limit %d" % (order, limit))
    want = {r[0]: r[1] for r in c.execute(q)}
    found = {}
    for jid, uj in c.execute("select job_id, urls_json from mix_jobs where urls_json is not null"):
        try:
            us = json.loads(uj) or []
        except Exception:                      # noqa: BLE001
            continue
        for i, u in enumerate(us):
            for sc in want:
                if sc in str(u) and sc not in found:
                    for p in (glob.glob(f"shopping_shorts/data/mix_jobs/{jid}/s{i}.mp4")
                              + glob.glob(f"shopping_shorts/data/mix_jobs/{jid}/s{i}/*.mp4")):
                        if os.path.getsize(p) > 50000:
                            found[sc] = (p, want[sc])
                            break
    return found


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


def run(db, top, seconds):
    groups = {"터진": files_for(db, top, "desc"), "대조": files_for(db, 400, "asc")}
    out = {}
    for name, fs in groups.items():
        rows = []
        for sc, (p, v) in fs.items():
            pr = profile(p, seconds)
            if pr:
                rows.append((sc, v) + pr)
        out[name] = rows
        print("%s군: 파일 있는 %d편 중 %d편 측정" % (name, len(fs), len(rows)))
    print("\n첫 %d초 · 중앙값 비교" % seconds)
    print("  %-5s %7s %10s %9s" % ("군", "움직임", "첫1초비중", "컷전환수"))
    for name, rows in out.items():
        if not rows:
            continue
        print("  %-5s %7.2f %9.1f%% %9.1f" % (name, med([r[2] for r in rows]),
                                              med([r[3] for r in rows]), med([r[4] for r in rows])))
    print("\n터진군 상위 8편")
    for sc, v, m, f1, sp in sorted(out["터진"], key=lambda r: -r[1])[:8]:
        print("  %-12s %9s회  움직임 %6.2f · 첫1초 %5.1f%% · 컷 %d" % (sc, f"{v:,}", m, f1, sp))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="shopping_shorts/data/reference.db")
    ap.add_argument("--top", type=int, default=114)
    ap.add_argument("--seconds", type=float, default=3.0)
    a = ap.parse_args()
    run(a.db, a.top, a.seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
