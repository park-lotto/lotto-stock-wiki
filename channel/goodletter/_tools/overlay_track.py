# -*- coding: utf-8 -*-
"""굿레터 틀 층 켜짐/꺼짐 구간 재기(관제 097) — 10fps 로 칸마다 주황·흰 픽셀 수를 세어 켜진 구간을 낸다.
    py overlay_track.py <mp4> [--fps 10]  → JSON(칸별 켜진 구간 [t0,t1])
칸(1080×1920 기준, sMx9RWuifCA 실측): 제품 꼬리표 = 창 왼쪽 위 주황 알약(x0~420,y480~560) · P.S. 줄 = 주황 손글씨(y1660~1730)
· 링크 줄 = y1785~1845 · 출처 줄 = y1575~1635 · 워터마크 = 창 오른쪽 위(x820~1075,y480~560 흰)."""
import sys, json
import cv2, numpy as np

ZONES = {"product_tag": ((0, 420, 480, 560), "orange", 400),
         "ps_line": ((0, 1080, 1660, 1730), "orange", 500),
         "link_line": ((0, 1080, 1785, 1845), "white", 300),
         "source_line": ((0, 1080, 1575, 1635), "white", 300)}


def count(f, kind):
    b, g, r = [f[..., i].astype(int) for i in range(3)]
    if kind == "orange":
        return int(((r > 200) & (g > 80) & (g < 175) & (b < 80)).sum())
    return int(((r > 200) & (g > 200) & (b > 200)).sum())


def track(mp4, fps=10):
    cap = cv2.VideoCapture(mp4); src = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(src / fps))); i = 0; on = {k: [] for k in ZONES}
    while True:
        ok, f = cap.read()
        if not ok: break
        if i % step == 0:
            t = round(i / src, 2)
            for k, ((x0, x1, y0, y1), kind, th) in ZONES.items():
                on[k].append((t, count(f[y0:y1, x0:x1], kind) >= th))
        i += 1
    out = {}
    for k, seq in on.items():
        spans, s = [], None
        for t, v in seq:
            if v and s is None: s = t
            if not v and s is not None: spans.append([s, t]); s = None
        if s is not None: spans.append([s, seq[-1][0]])
        out[k] = [sp for sp in spans if sp[1] - sp[0] >= 0.2]
    return out


if __name__ == "__main__":
    print(json.dumps(track(sys.argv[1]), ensure_ascii=False))
