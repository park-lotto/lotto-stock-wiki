# -*- coding: utf-8 -*-
"""업체 기본/고급 동작 탐침 (2026-09-28 사장님 "내꺼 테스트 조각 돌려봐, 기본이나 고급만 되고 그런 건 없지?").

짧은 조각 하나(기본 1.5초)를 사장님 키로 기본·고급 각각 1회 보낸다. 걸린 시간·결과·오류 원문을 찍는다.
업체가 한쪽 등급만 멈추는지 가린다. 과금: 기본 올림 2초×2 + 고급 2초×4 = 약 12크레딧.
실행(트랙 폴더): py shopping_shorts/scripts/vmake_tier_probe.py --keyfile <키> --src <영상> --out <폴더>
"""
import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser()
ap.add_argument("--keyfile", required=True); ap.add_argument("--src", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--start", type=float, default=2.0); ap.add_argument("--dur", type=float, default=1.5)
ap.add_argument("--timeout-min", type=float, default=25.0)
a = ap.parse_args()
from shopping_shorts import vmake_client as vc     # noqa: E402

key = [k for k in Path(a.keyfile).read_text(encoding="utf-8").splitlines() if k.strip()][0]
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
piece = out / "probe_in.mp4"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % a.start, "-i", a.src, "-t", "%.3f" % a.dur,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", str(piece)], check=True)
res = {}


def run(tier):
    t0 = time.time()
    try:
        p = vc.remove_subtitles(str(piece), key, str(out / ("probe_%s.mp4" % tier)), tier=tier)
        res[tier] = ("성공", round(time.time() - t0, 1), Path(p).stat().st_size)
    except Exception as e:                        # noqa: BLE001
        res[tier] = ("실패", round(time.time() - t0, 1), str(e)[:300])


ths = [threading.Thread(target=run, args=(t,), daemon=True) for t in ("basic", "pro")]
for t in ths:
    t.start()
deadline = time.time() + a.timeout_min * 60
for t in ths:
    t.join(max(0, deadline - time.time()))
for tier in ("basic", "pro"):
    print(tier, res.get(tier, ("시간초과(%.0f분 안에 안 끝남)" % a.timeout_min,)))
