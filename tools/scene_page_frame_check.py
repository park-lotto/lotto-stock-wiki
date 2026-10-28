# -*- coding: utf-8 -*-
"""장면꾸미기 페이지 그림 검사 (관제 101) — 편집기 각 페이지 그림이 **그 페이지 시각의 실제 화면**인가.

재는 법(결과물 대조): 페이지마다 편집기가 받는 그림(_beatframe_file(at=페이지 시각))을, 같은 시각의 기준 영상 프레임과
작은 흑백 그림(32x56)으로 견준다. 종전 그림(칸 대표 그림 한 장)도 같이 재서 얼마나 달랐는지 보여준다.
기준 영상 = 렌더와 같은 입력으로 조립한 clean_preview.mp4(자막제거 작업) 또는 --ref 로 준 영상(같은 시간축, 꾸밈 없는 것).

실행: py tools/scene_page_frame_check.py --job <job_id> [--db <DB>] [--work-root <폴더>] [--ref <영상>] [--max 30.0]
끝 코드: 페이지 그림이 기준과 다른 장면(평균 차 > --max)이면 1.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHORTS_CLEAN_FINAL", "1")
ap = argparse.ArgumentParser()
ap.add_argument("--job", required=True)
ap.add_argument("--db", default="")
ap.add_argument("--work-root", default="")
ap.add_argument("--ref", default="")
ap.add_argument("--max", type=float, default=30.0)     # 같은 장면도 확대·띠 때문에 10~25 차이가 난다(실측), 다른 장면은 40~90
a = ap.parse_args()
sys.argv = [sys.argv[0]]

from shopping_shorts import config as cfg          # noqa: E402
if a.db:
    cfg.DB_PATH = a.db
from shopping_shorts import app as A               # noqa: E402
from shopping_shorts import video_assemble as va   # noqa: E402
from shopping_shorts.scene_style import context_for  # noqa: E402
from shopping_shorts.store import Store            # noqa: E402

if a.db:
    A.DB_PATH = a.db
if a.work_root:
    A._MIX_WORK_DIR = Path(a.work_root)
W, H = 32, 56


def gray(path, t=None):
    seek = [] if t is None else ["-ss", "%.3f" % t]
    raw = subprocess.run(["ffmpeg", "-v", "error"] + seek + ["-i", str(path), "-frames:v", "1",
                          "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,scale=%d:%d,format=gray" % (W, H),
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    return raw if len(raw) == W * H else None


def diff(x, y):
    return sum(abs(p - q) for p, q in zip(x, y)) / float(W * H)


def main():
    job = Store(cfg.DB_PATH).get_mix_job(a.job)
    assert job and job.get("edit_plan"), "작업 없음"
    work = A._MIX_WORK_DIR / a.job
    ref = Path(a.ref) if a.ref else work / "clean_preview.mp4"
    assert ref.exists(), "기준 영상 없음: %s" % ref
    plan = job["edit_plan"]
    tts = {b["beat_idx"]: b["tts_path"] for b in plan["beats"] if b.get("tts_path")}
    scenes = context_for(va._beat_timeline(plan, tts), dict(job.get("headcopy") or {}),
                         (job.get("deco") or {}).get("scene_style"), a.job)["scenes"]
    bad, worse_old, rows = 0, 0, []
    for k, sc in enumerate(scenes):
        at = A._scene_page_time(sc)
        new = A._beatframe_file(job, a.job, int(sc["beat_idx"]), at=at)
        old = A._beatframe_file(job, a.job, int(sc["beat_idx"]))
        r = gray(ref, at)
        gn, go = (gray(new) if new else None), (gray(old) if old else None)
        if r is None or gn is None:
            rows.append((k, sc, at, None, None))
            bad += 1
            continue
        dn = diff(gn, r)
        do = diff(go, r) if go is not None else None
        bad += dn > a.max
        worse_old += bool(do is not None and do > a.max)
        rows.append((k, sc, at, dn, do))
    for k, sc, at, dn, do in rows:
        print("  %2d쪽 칸%-2s %5.2f초 %-16s 새 그림 차 %s · 종전(칸 그림) 차 %s%s" % (
            k + 1, sc["beat_idx"], at, (sc.get("caption") or "")[:16],
            "측정불가" if dn is None else "%5.1f" % dn, "-" if do is None else "%5.1f" % do,
            "  ← 다른 장면" if (dn is None or dn > a.max) else ""))
    print("== 페이지 %d · 새 그림이 기준과 다른 장면 %d · 종전 그림이 다른 장면이던 페이지 %d (문턱 %.1f)" % (
        len(rows), bad, worse_old, a.max))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
