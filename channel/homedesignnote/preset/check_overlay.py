# -*- coding: utf-8 -*-
"""두유노홈디노 프리셋 렌더 대조 — 원본 프레임 vs 우리 렌더(같은 시각)의 자막·브랜드 자리 잉크를 잰다.

    PYTHONUTF8=1 py channel/homedesignnote/preset/check_overlay.py <원본.mp4> <우리.mp4> <초> [--out 시트.png]

잰 것(띠마다): 밝은 잉크(>225) 상자 x0·x1·y0·y1·폭·높이 / 잉크 밖 12~40px 고리 평균 밝기 · 40~80px 바탕 밝기 · halo = 바탕−고리(검정 번짐 세기) / 잉크 안 평균 색.
자막 띠 = y 420~760(원본 자막 자리 두 무리 483·585 포함), 브랜드 띠 = y 1395~1505(원본 워터마크 1423~1475).
우리 렌더는 원본 자막·워터마크를 칠로 가린 재료(clean)에 그린 것이어야 한다 — 겹쳐 그리면 잉크가 섞인다.
"""
import sys, json
import cv2, numpy as np

BANDS = {"caption": (420, 760), "brand": (1395, 1505)}


def grab(p, t):
    cap = cv2.VideoCapture(p); cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, im = cap.read()
    if not ok:
        raise SystemExit(f"프레임 못 읽음 {p} {t}")
    return im


def measure(im, band):
    y0, y1 = band; a = im[y0:y1].astype(np.float32); g = a.mean(2)
    ink = (a.min(2) > 225)
    # 작은 점 잡음 제거
    n, lab, st_, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), 8)
    keep = np.zeros_like(ink)
    for k in range(1, n):
        if st_[k, cv2.CC_STAT_AREA] >= 6:
            keep[lab == k] = True
    ys, xs = np.nonzero(keep)
    if len(xs) < 30:
        return None
    k1 = cv2.dilate(keep.astype(np.uint8), np.ones((25, 25), np.uint8)); k2 = cv2.dilate(keep.astype(np.uint8), np.ones((81, 81), np.uint8))
    ring = (k2 > 0) & (k1 == 0)
    k3 = cv2.dilate(keep.astype(np.uint8), np.ones((161, 161), np.uint8))
    outer = (k3 > 0) & (k2 == 0)   # 번짐 밖 바탕(40~80px 고리) — 번짐 세기 = 바탕 − 고리
    return {"x0": int(xs.min()), "x1": int(xs.max()), "y0": int(ys.min()) + y0, "y1": int(ys.max()) + y0,
            "w": int(xs.max() - xs.min()), "h": int(ys.max() - ys.min()), "ink_px": int(keep.sum()),
            "ring_lum": round(float(g[ring].mean()), 1), "outer_lum": round(float(g[outer].mean()), 1) if outer.any() else None,
            "halo": round(float(g[outer].mean() - g[ring].mean()), 1) if outer.any() else None, "fill": [int(v) for v in a[keep].mean(0)[::-1]]}


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    src, ours, t = a[0], a[1], float(a[2])
    A, B = grab(src, t), grab(ours, t)
    rows = {k: {"orig": measure(A, b), "ours": measure(B, b)} for k, b in BANDS.items()}
    print(json.dumps({"t": t, **rows}, ensure_ascii=False, indent=1))
    if "--out" in sys.argv:
        o = sys.argv[sys.argv.index("--out") + 1]
        crops = []
        for k, (y0, y1) in BANDS.items():
            crops += [A[y0:y1], B[y0:y1]]
        ok, buf = cv2.imencode(".png", np.vstack(crops)); open(o, "wb").write(buf.tobytes())  # 한글 경로(cv2.imwrite 실패)


if __name__ == "__main__":
    main()
