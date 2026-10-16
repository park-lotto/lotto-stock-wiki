# -*- coding: utf-8 -*-
"""외곽선 고리 밝기 눈금: 글자에서 1~24px 고리마다 밝기 중앙값 + 현재 glyph_style 외곽선 px.
    py tools/calcopy/engine/analyze4_check/outline_profile.py <mp4> <y0> <y1> <bright|dark> <초,초,...>
"""
import sys, numpy as np, cv2
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shopping_shorts.channelkit.bench import probe
from shopping_shorts.channelkit.bench.layout import ink_fill, lum
from shopping_shorts.channelkit.bench import captions as C
p, y0, y1, pol = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
for t in [float(x) for x in sys.argv[5].split(",")]:
    img = probe.grab(p, t, f"crop=1080:{y1-y0}:0:{y0}", 1080, y1-y0)
    L = lum(img); ink = ink_fill(img, pol)
    prof=[]; prev=ink
    for r in range(1, 25):
        d = cv2.dilate(ink.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*r+1,2*r+1)))>0
        rr = d & ~prev; prev = d
        prof.append(int(np.median(L[rr])) if rr.any() else -1)
    g = C.glyph_style(img, pol, [0,0,0])
    print(t, "ink", int(L[ink].mean()), "prof", prof, "ol", g and g["outline_px"])
