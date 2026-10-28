# -*- coding: utf-8 -*-
"""극성 증거 눈금: 영상 한 편의 띠 크롭(시각 여러 개)마다 (옛 채움비, 어두운 화소 둘레 중 큰 밝은 바탕 비율, 좌우 여백 밝기).
    py tools/calcopy/engine/analyze4_check/polarity_probe.py <mp4> <y0> <y1> <초,초,...>
(4판 실측: 흰 바탕 검정 글자 둘레비 0.76~0.88 · 영상 위 외곽선 글자 0.00~0.08)
"""
import sys, numpy as np, cv2
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shopping_shorts.channelkit.bench import probe
from shopping_shorts.channelkit.bench.layout import ink_fill, ink_mask, lum
from shopping_shorts.channelkit.bench.constants import INK_DARK, INK_BRIGHT
def metrics(path, y0, y1, times):
    W = 1080; out=[]
    for t in times:
        img = probe.grab(path, t, f"crop={W}:{y1-y0}:0:{y0}", W, y1-y0)
        if img is None: continue
        L = lum(img)
        fb = ink_fill(img, "bright") & ~ink_mask(img, "dark")
        near = cv2.dilate(fb.astype(np.uint8), np.ones((17,17),np.uint8)) > 0
        dk = (L < INK_DARK) & near
        r = fb.sum()/max(1,dk.sum())
        dark = (L < INK_DARK).astype(np.uint8)
        ring = (cv2.dilate(dark, np.ones((5,5),np.uint8))>0) & (dark==0)
        br = (L > INK_BRIGHT).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(br, 8)
        big = np.zeros(n,bool); big[1:] = st[1:, cv2.CC_STAT_AREA] >= 0.15*L.size
        ringbig = (ring & big[lab]).sum()/max(1,ring.sum())
        marg = np.concatenate([L[:, :30].ravel(), L[:, -30:].ravel()])
        out.append((round(float(r),3), round(float(ringbig),3), round(float(np.median(marg)),1)))
    return out
if __name__ == "__main__":
    p, y0, y1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    ts = [float(x) for x in sys.argv[4].split(",")]
    for m in metrics(p, y0, y1, ts): print(m)
