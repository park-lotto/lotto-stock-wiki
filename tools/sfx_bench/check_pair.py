# -*- coding: utf-8 -*-
"""팩 있음/없음 두 판 대조 — 목소리 크기 불변 · 효과음 개수·시각·크기(이븐쇼핑 대비).
사용: py tools/sfx_bench/check_pair.py <with.mp4> <without.mp4> <plan.json>"""
import json, sys, subprocess, collections
import numpy as np
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SR = 44100
def load(p):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.float32).astype(float)
w, o = load(sys.argv[1]), load(sys.argv[2])
# ★정렬: 팩 없는 판은 음성을 복사(-c:a copy)하고 팩 있는 판은 AAC로 다시 굽는다 → 인코더 지연
#   (약 1024샘플)만큼 어긋난다. 안 맞추면 목소리가 안 지워져 효과음을 하나도 못 찾는다(실측).
from scipy.signal import fftconvolve
seg = int(8 * SR); c = fftconvolve(w[:seg], o[:seg][::-1], "full"); lag = int(np.argmax(c)) - (seg - 1)
if lag > 0: w = w[lag:]
elif lag < 0: o = o[-lag:]
n = min(len(w), len(o)); w, o = w[:n], o[:n]
print(f"정렬 {lag} 샘플({lag / SR * 1000:.1f}ms)")
P = json.load(open(sys.argv[3], encoding="utf-8")); plan = [(e[0], e[1]) for e in P["events"]]
res = w - o
fr = int(0.05 * SR)
def med(a):
    v = 20 * np.log10(np.sqrt((a[:len(a) // fr * fr].reshape(-1, fr) ** 2).mean(1)) + 1e-9)
    return float(np.median(v[v > v.max() - 40]))
# 목소리 크기: 효과음 없는 구간(각 효과음 0.4초 밖)만 비교
mask = np.ones(n, bool)
for _, t in plan:
    mask[max(0, int(t * SR) - 2000):int((t + 0.45) * SR)] = False
vw, vo = med(w[mask]), med(o[mask])
print(f"목소리 크기(효과음 밖 구간): 팩있음 {vw:.2f}dB · 팩없음 {vo:.2f}dB · 차이 {vw - vo:+.2f}dB")
k = int(0.005 * SR); r = 20 * np.log10(np.sqrt(np.convolve(res ** 2, np.ones(k) / k, "same")) + 1e-9)
fl = np.percentile(r, 50); on = r > fl + 18; ev = []; i = 0
while i < len(on):
    if on[i]:
        j = i
        while j < len(on) and on[j:j + int(0.03 * SR)].any(): j += 1
        ev.append((i / SR, float(r[i:j].max()))); i = j
    else:
        i += 1
hit = [(s, t, min((e[0] for e in ev if abs(e[0] - t) <= 0.05), key=lambda x: abs(x - t)) - t) for s, t in plan if any(abs(e[0] - t) <= 0.05 for e in ev)]
miss = [(s, round(t, 2)) for s, t in plan if not any(abs(e[0] - t) <= 0.05 for e in ev)]
extra = [(round(e[0], 2), round(e[1], 1)) for e in ev if not any(-0.02 <= e[0] - t <= 1.1 for _, t in plan)]
print(f"계획 {len(plan)}발 · 찾음 {len(hit)} · 못찾음 {miss} · 계획밖 {extra}")
if hit:
    d = np.array([h[2] for h in hit]) * 1000; print(f"시각 오차 중앙 {np.median(d):+.0f}ms · 최대 {np.abs(d).max():.0f}ms")
EVEN = {"opener": -8.8, "dung": -7.0, "pop": -11.9, "ding": -14.7, "whoosh": -20.2, "tick": -22.4, "click2": -20.6}; EV = -17.5
lv = collections.defaultdict(list); kk = int(0.02 * SR)
for s, t in plan:
    seg = res[int(t * SR):int(t * SR) + int(0.3 * SR)]
    if len(seg) > kk: lv[s].append(float(20 * np.log10(np.sqrt(np.convolve(seg ** 2, np.ones(kk) / kk, "valid")).max() + 1e-9)))
for s in EVEN:
    if lv[s]: print(f"  {s:7s} {len(lv[s]):2d}발 목소리 대비 {np.median(lv[s]) - vo:+5.1f} (이븐쇼핑 {EVEN[s] - EV:+5.1f}) 차이 {np.median(lv[s]) - vo - (EVEN[s] - EV):+4.1f}dB")
print(f"최대음량: 팩있음 {20 * np.log10(np.abs(w).max()):.1f}dB · 팩없음 {20 * np.log10(np.abs(o).max()):.1f}dB")
