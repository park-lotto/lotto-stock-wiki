# -*- coding: utf-8 -*-
"""08 전기자전거 — render_front 완성본 소리를 −14 LUFS·트루피크 ≤ −1.5 dBTP 로 한 번 더 맞춘다(화면은 그대로 복사).
render_front 기본 리미터(0.89)로는 트루피크가 −0.2 로 넘어서(10-21 실측) 편 폴더에서만 맞춘다(공용 코드 안 고침).
    PYTHONUTF8=1 py 마스터_w3.py <in.mp4> <out.mp4>"""
import re, subprocess, sys

def meas(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", p, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]); tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])
    return I, tp

src, out = sys.argv[1], sys.argv[2]
I0, tp0 = meas(src)
g, lim = round(-14.0 - I0, 2), 0.70   # 리미터 −3.1 dB(샘플) → aac 뒤 트루피크 여유
for _ in range(8):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-map", "0:v", "-map", "0:a", "-c:v", "copy",
                    "-af", f"aresample=192000,volume={g}dB,alimiter=limit={lim}:attack=2:release=50:level=false,aresample=48000",
                    "-c:a", "aac", "-b:a", "192k", out], check=True)
    I, tp = meas(out)
    print(f"gain {g} limit {lim} → I {I} TP {tp}")
    if abs(I + 14.0) <= 0.3 and tp <= -1.5:
        break
    if tp > -1.5:
        lim = round(lim * 0.93, 3)
    g = round(g + (-14.0 - I), 2)
print({"in": [I0, tp0], "out": [I, tp]})
