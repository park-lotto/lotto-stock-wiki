# -*- coding: utf-8 -*-
"""06 완성본 마스터 — render_front 결과(앞 편 LUFS −15.5 에 맞춘 것)를 워커 브리프 기준 −14 LUFS·참피크 ≤ −1.5 dBTP 로.
화면은 그대로(-c:v copy), 소리만 loudnorm 2회(측정 → linear 적용). 결과 = render/final_m14.mp4 + 바탕화면 복사(MD5 대조).
    PYTHONUTF8=1 py channel/hottemreport/현장썰하이브리드/06_아이언맨헬멧/master.py
"""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

W = Path("C:/숏템_칼카피/hottemreport/현장썰하이브리드/06_아이언맨헬멧/render")
SRC, OUT = W / "final.mp4", W / "final_m14.mp4"
DESK = Path("C:/Users/CH/Desktop/칼카피영상/숏템리폿/하이브리드/칼카피_숏템리폿_아이언맨헬멧_하이브리드_1차.mp4")
I = -14.0


def run(c):
    return subprocess.run([str(x) for x in c], capture_output=True, text=True, encoding="utf-8", errors="replace")


def measure(p):
    e = run(["ffmpeg", "-hide_banner", "-i", p, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])


# loudnorm linear 은 참피크에 막혀 −14.7 에 멈췄다(10-21 실측) → 소리 올림 + 리미터(−2.5 dB — −2 dB 는 aac 뒤 참피크 −1.4)로 맞춘다(render_front 와 같은 꼴, 6회까지)
g = round(I - measure(SRC)[0], 2)
for _ in range(6):
    r = run(["ffmpeg", "-y", "-i", SRC, "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af",
             f"volume={g}dB,alimiter=limit=0.75:attack=1:release=40:level=false,aresample=48000", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", OUT])
    assert r.returncode == 0, r.stderr[-800:]
    lu, pk = measure(OUT)
    if abs(lu - I) <= 0.2:
        break
    g = round(g + (I - lu), 2)
lu, pk = measure(OUT)
print("before", measure(SRC), "after", (lu, pk))
DESK.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(OUT, DESK)
md5 = [hashlib.md5(Path(p).read_bytes()).hexdigest() for p in (OUT, DESK)]
print("desktop", DESK, md5[0], "same" if md5[0] == md5[1] else "DIFF")
