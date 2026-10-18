# -*- coding: utf-8 -*-
"""키치잇판 성시경 신라면 — 쓰는 구간만 받기(원본은 지워져 다시 받음). 구간마다 파일 하나 = <id>_<시작초>.mp4 (파일 0초 = 원본 시작초).
    PYTHONUTF8=1 py channel/kitchit/하이브리드_성시경/fetch.py"""
import concurrent.futures as cf, subprocess, sys
from pathlib import Path
DST = Path("C:/숏템_칼카피/kitchit/sinramen/src")
SPANS = {"Wy9--jw0ZsM": [(10, 27), (44, 58), (94, 99.5), (150, 172), (182, 212), (255, 262), (272, 278)],
         "-o8gedIaYmA": [(5, 15), (23, 30), (108, 130)]}
FMT = "137+ba[ext=m4a]/bv*[height>=1080]+ba/b"
def one(vid, a, b):
    out = DST / f"{vid}_{a:g}.mp4"
    if out.exists() and out.stat().st_size > 100000: return out.name, "있음"
    r = subprocess.run(["yt-dlp", "-f", FMT, "--download-sections", f"*{a}-{b}", "--force-keyframes-at-cuts", "--merge-output-format", "mp4",
                        "-o", str(out), "--", f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.name, "OK" if out.exists() else r.stderr[-300:]
with cf.ThreadPoolExecutor(3) as ex:
    for f in [ex.submit(one, v, a, b) for v, sp in SPANS.items() for a, b in sp]:
        print(*f.result(), flush=True)
