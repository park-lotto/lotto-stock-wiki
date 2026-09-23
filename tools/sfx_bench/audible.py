# -*- coding: utf-8 -*-
"""효과음마다 '그 순간' 목소리 대비 크기(들리는가) — 두 판 대조.
사용: py tools/sfx_bench/audible.py <with.mp4> <without.mp4> <plan.json>
기준: 효과음 20ms 최대 − 같은 0.3초 목소리 RMS. +3dB 미만이면 '묻힘 의심'."""
import json, sys, subprocess
import numpy as np
from scipy.signal import fftconvolve
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SR = 44100
def load(p):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.float32).astype(float)
w, o = load(sys.argv[1]), load(sys.argv[2])
seg = int(8 * SR); c = fftconvolve(w[:seg], o[:seg][::-1], "full"); lag = int(np.argmax(c)) - (seg - 1)
w = w[lag:] if lag > 0 else w; o = o[-lag:] if lag < 0 else o; n = min(len(w), len(o)); w, o = w[:n], o[:n]; r = w - o
ev = json.load(open(sys.argv[3], encoding="utf-8"))["events"]
k = int(0.02 * SR); low = 0
print("시각    소리     효과음최대  그순간목소리  차이   판정")
for s, t, txt in ev:
    a = int(t * SR); b = a + int(0.3 * SR)
    sp = 20 * np.log10(np.sqrt(np.convolve(r[a:b] ** 2, np.ones(k) / k, "valid")).max() + 1e-9)
    vr = 20 * np.log10(np.sqrt((o[a:b] ** 2).mean()) + 1e-9)
    d = sp - vr; bad = d < 3; low += bad
    print(f"{t:6.2f}  {s:7s} {sp:7.1f}dB   {vr:7.1f}dB   {d:+5.1f}  {'묻힘 의심' if bad else '들림'}  {txt[:14]}")
print(f"묻힘 의심 {low}/{len(ev)}발")
