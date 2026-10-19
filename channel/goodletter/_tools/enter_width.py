# -*- coding: utf-8 -*-
"""굿레터 자막 등장 모양 재기(관제 097) — 줄 시작 근처 60fps 프레임마다 자막 잉크 폭·높이를 잰다.
    py enter_width.py <mp4> <y0> <y1> <t> [<t> ...]  → 줄마다 프레임별 (초, 폭, 높이) + 판정
잉크 = 밝은 흰/노랑 채움 바로 옆에 검정 외곽이 있는 픽셀(굿레터 자막 꼴). 판정:
  pop     = 첫 잉크 프레임 폭 < 최종 폭의 60% 이고, 중간에 최종 폭의 105% 이상 넘침
  grow    = 첫 잉크 폭 < 60% 이나 넘침 없음
  instant = 첫 잉크 프레임부터 최종 폭의 90% 이상
최종 폭 = 시작 뒤 0.25~0.35초 프레임 폭 중앙값. 그림이 아니라 숫자로 남기는 도구(눈 판독의 보조)."""
import sys, json
import cv2, numpy as np


def ink(band):
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    v, s, h = hsv[..., 2], hsv[..., 1], hsv[..., 0]
    bright = (v > 200) & ((s < 70) | ((h > 12) & (h < 35) & (s > 90)))
    dark = cv2.dilate((v < 45).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    m = (bright & dark).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    cols = np.where(m.sum(0) >= 2)[0]; rows = np.where(m.sum(1) >= 2)[0]
    if len(cols) < 5 or m.sum() < 80:
        return 0, 0
    return int(cols[-1] - cols[0]), int(rows[-1] - rows[0])


def measure(mp4, y0, y1, t, pre=0.08, post=0.40):
    cap = cv2.VideoCapture(mp4); fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(round((t - pre) * fps))))
    out = []
    while True:
        ok, f = cap.read()
        if not ok: break
        tt = cap.get(cv2.CAP_PROP_POS_FRAMES) / fps - 1 / fps
        if tt > t + post: break
        w, h = ink(f[y0:y1])
        out.append((round(tt, 3), w, h))
    cap.release()
    fin = [w for tt, w, h in out if t + 0.25 <= tt <= t + 0.35 and w > 0]
    W = float(np.median(fin)) if fin else 0
    # 앞 줄이 남아 있을 수 있다 → 시작 전후 빈 프레임(잉크 0) 다음 첫 잉크 프레임을 새 줄 시작으로 본다
    zeros = [i for i, (tt, w, h) in enumerate(out) if w == 0 and tt <= t + 0.2]
    i0 = zeros[-1] + 1 if zeros else 0
    first = next(((tt, w) for tt, w, h in out[i0:] if w > 0), None)
    kind = "?"
    if W and first:
        peak = max(w for tt, w, h in out if tt <= t + 0.25)
        if first[1] < 0.6 * W:
            kind = "pop" if peak >= 1.05 * W else "grow"
        elif first[1] >= 0.9 * W:
            kind = "instant"
        else:
            kind = "mid"
        settle = next((tt for tt, w, h in out if tt > first[0] and abs(w - W) <= 0.03 * W and tt > first[0] + 0.03), None)
        return {"t": t, "kind": kind, "first": first, "final_w": W, "peak_ratio": round(peak / W, 2),
                "enter_ms": int(round((settle - first[0]) * 1000)) if settle else None, "frames": out}
    return {"t": t, "kind": kind, "first": first, "final_w": W, "frames": out}


if __name__ == "__main__":
    mp4, y0, y1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    res = [measure(mp4, y0, y1, float(t)) for t in sys.argv[4:]]
    for r in res:
        print(r["t"], r["kind"], "첫", r.get("first"), "최종폭", r.get("final_w"), "넘침", r.get("peak_ratio"), "ms", r.get("enter_ms"))
