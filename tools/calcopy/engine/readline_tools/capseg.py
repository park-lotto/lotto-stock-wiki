# -*- coding: utf-8 -*-
"""자막 띠 분할(capseg) — 30fps 매 프레임 글자 잉크 마스크가 바뀌는 지점으로 자막 덩어리를 자른다. 글자 꼴마다 모드가 있다.

어디서 왔나(알고리즘은 각각 그대로 옮김):
  mode=color  06 잇템로그 워커 capseg.py(10-24) — '검정 외곽 옆 밝은 채움'(V>185 & 검정 V<45 9x9 팽창). 색·흰 채움 + 검정 외곽. 기본값.
  mode=bright/dark/both  06 썰풀다 워커 seg2.py(10-25) — bright = 흰 저채도 채움(V>200·S<70) + 검정 외곽, dark = 검정 글(V<60) 옆 흰,
              both = 둘 다. 마스크 2px 간격, 잉크 >80, yr 2px 단위.
  capseg_box  06 유머쇼쇼 워커 seg2.py(10-25) — 흰 상자 위 검정 글(외곽 없음): 흰 행(흰 비율>0.45) ±7행 안 어두운 픽셀 = 잉크,
              IoU 차>0.35 또는 잉크가 10%·60칸 넘게 늘면(한 줄씩 덧붙는 자막) 새 덩어리, 2프레임 이하 조각은 앞 덩어리에 붙임.
              출력 꼴이 다르다(lines_y·ink_x·first_frac·enter_fr·append).
입력: mp4 · 띠 y0 y1 (예: 잇템로그 1150 1460) · [--mode color|bright|dark|both|box]
출력(json 목록): color/bright/dark/both → [{t0, t1, n, ink, hex, yr}] · box → [{t0, t1, n, lines_y, ink_x, hex, first_frac, enter_fr, append}]
crop 은 exact=1 — yuv420 원본은 홀수 y·높이를 ffmpeg 가 짝수로 내려 잘라 프레임 크기가 어긋나고 reshape 가 프레임을 밀어 쓰레기가 된다
(10-25 실측: 띠 1137~1462(높이 325) → 실제 324줄 → 경계 39개 중 20개 어긋남). 짝수 띠는 exact 유무와 출력이 같다.

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/capseg.py <mp4> <y0> <y1> <out.json> [--mode color]
"""
from __future__ import annotations

import json
import subprocess
import sys

import cv2
import numpy as np

MODES = ("color", "bright", "dark", "both", "box")


def _diff(a, b):
    u = (a | b).sum()
    return 0 if u == 0 else 1 - (a & b).sum() / u


def read_band(mp4: str, y0: int, y1: int, width: int = 1080, pix: str = "bgr24", scale: tuple | None = None) -> np.ndarray:
    H = y1 - y0
    vf = f"crop={width}:{H}:0:{y0}:exact=1" + (f",scale={scale[0]}:{scale[1]}" if scale else "")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", vf, "-f", "rawvideo", "-pix_fmt", pix, "-"], capture_output=True).stdout
    w, h = scale if scale else (width, H)
    n = len(raw) // (w * h * 3)
    return np.frombuffer(raw, np.uint8)[:n * w * h * 3].reshape(n, h, w, 3)


def capseg(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080, mode: str = "color", frames: np.ndarray | None = None) -> list[dict]:
    """frames 를 주면(이미 자른 띠 [n,H,W,3] bgr) 읽기를 건너뛴다 — 띠 찾기·시험용."""
    if mode == "box":
        return capseg_box(mp4, y0, y1, fps=fps, width=width)
    F = read_band(mp4, y0, y1, width) if frames is None else frames
    if mode == "color":
        return _seg_color(F, y0, fps)
    if mode in ("bright", "dark", "both"):
        return _seg_pol(F, y0, mode, fps)
    raise ValueError(f"mode {mode} — {MODES}")


def _seg_color(F: np.ndarray, y0: int, fps: float) -> list[dict]:
    n, H = F.shape[0], F.shape[1]
    k = np.ones((9, 9), np.uint8)
    masks = []
    cols = []
    for f in F:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        v = hsv[..., 2]
        dark = (v < 45).astype(np.uint8)
        near = cv2.dilate(dark, k) > 0
        fill = ((v > 185) & near)
        m = fill.astype(np.uint8)
        masks.append(cv2.resize(m * 255, (270, max(1, H // 4)), interpolation=cv2.INTER_AREA) > 40)
        if m.sum() > 200:
            px = f[m > 0]
            cols.append(np.median(px, 0).astype(int).tolist())
        else:
            cols.append(None)
    cnt = [int(m.sum()) for m in masks]
    segs = []
    start = 0
    for i in range(1, n):
        d = _diff(masks[i], masks[i - 1])
        if d > 0.45 and (cnt[i] > 30 or cnt[i - 1] > 30):
            segs.append((start, i))
            start = i
    segs.append((start, n))
    res = []
    for a, b in segs:
        mid = (a + b) // 2
        c = [cc for cc in cols[a:b] if cc]
        col = np.median(np.array(c), 0).astype(int).tolist() if c else None
        hexs = "#%02X%02X%02X" % (col[2], col[1], col[0]) if col else None
        ys = np.where(masks[mid].any(1))[0]
        res.append({"t0": round(a / fps, 3), "t1": round(b / fps, 3), "n": b - a, "ink": cnt[mid], "hex": hexs,
                    "yr": [int(y0 + ys.min() * 4), int(y0 + ys.max() * 4)] if len(ys) else None})
    return res


def _seg_pol(F: np.ndarray, y0: int, mode: str, fps: float) -> list[dict]:
    n = F.shape[0]
    k = np.ones((7, 7), np.uint8)

    def mask(f):
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        V = hsv[..., 2]
        S = hsv[..., 1]
        br = ((V > 200) & (S < 70)).astype(np.uint8)
        dk = (V < 60).astype(np.uint8)
        m = np.zeros(V.shape, bool)
        if mode in ("both", "bright"):
            m |= (br > 0) & (cv2.dilate(dk, k) > 0)
        if mode in ("both", "dark"):
            m |= (dk > 0) & (cv2.dilate(br, k) > 0)
        return m[::2, ::2]
    M = [mask(F[i]) for i in range(n)]
    ink = np.array([m.sum() for m in M])
    segs = []
    s = 0
    for i in range(1, n):
        if _diff(M[i], M[i - 1]) > 0.45 and (ink[i] > 80 or ink[i - 1] > 80):
            segs.append((s, i))
            s = i
    segs.append((s, n))
    res = []
    for a, b in segs:
        mid = (a + b) // 2
        f = F[mid]
        m = np.zeros(f.shape[:2], bool)
        mm = M[mid]
        m[::2, ::2] = mm
        hx = None
        yr = None
        if mm.sum() > 0:
            c = np.median(f[m], 0).astype(int)
            hx = "#%02X%02X%02X" % (c[2], c[1], c[0])
            ys = np.where(m.any(1))[0]
            yr = [int(y0 + ys.min()), int(y0 + ys.max())]
        res.append({"t0": round(a / fps, 3), "t1": round(b / fps, 3), "n": b - a, "ink": int(ink[mid]), "hex": hx, "yr": yr})
    return res


def capseg_box(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080) -> list[dict]:
    W, H = 540, (y1 - y0) // 2
    F = read_band(mp4, y0, y1, width, pix="rgb24", scale=(W, H))
    n = F.shape[0]
    inks = []
    cnt = []
    for f in F:
        f = f.astype(int)
        V = f.max(2)
        S = V - f.min(2)
        wr = ((V > 220) & (S < 30)).mean(1) > 0.45
        wr2 = wr.copy()
        for d in range(1, 8):
            wr2[d:] |= wr[:-d]
            wr2[:-d] |= wr[d:]
        ink = (V < 100) & (S < 60) & wr2[:, None]
        inks.append(ink)
        cnt.append(int(ink.sum()))
    segs = []
    cur = None
    for i in range(n):
        has = cnt[i] > 40
        if cur is None:
            if has:
                cur = {"a": i}
            continue
        if not has:
            cur["b"] = i
            segs.append(cur)
            cur = None
            continue
        grow = cnt[i] > cnt[i - 1] * 1.10 and cnt[i - 1] > 0 and (inks[i - 1] & inks[i]).sum() > 0.9 * cnt[i - 1]
        if _diff(inks[i - 1], inks[i]) > 0.35 or (grow and cnt[i] - cnt[i - 1] > 60):
            cur["b"] = i
            segs.append(cur)
            cur = {"a": i}
    if cur:
        cur["b"] = n
        segs.append(cur)
    m = []
    for s in segs:
        if s["b"] - s["a"] <= 2 and m and m[-1]["b"] == s["a"]:
            m[-1]["b"] = s["b"]
            continue
        m.append(s)
    res = []
    prev = None
    for s in m:
        mid = (s["a"] + s["b"]) // 2
        ink = inks[mid]
        rows = np.where(ink.sum(1) > 0)[0]
        lines = []
        if len(rows):
            st = rows[0]
            pv = rows[0]
            for r in rows[1:]:
                if r - pv > 6:
                    lines.append((st, pv))
                    st = r
                pv = r
            lines.append((st, pv))
        lines = [(a, b) for a, b in lines if b - a >= 6]
        lx = []
        for a, b in lines:
            cols = np.where(ink[a:b + 1].sum(0) > 0)[0]
            lx.append([int(cols[0] * 2), int(cols[-1] * 2)] if len(cols) else None)
        f = F[mid].astype(int)
        px = f[ink]
        hexv = "#%02X%02X%02X" % tuple(np.median(px, 0).astype(int)) if len(px) else None
        a = s["a"]
        full = max(cnt[mid], 1)
        k = 0
        while a + k < s["b"] and cnt[a + k] < 0.9 * full:
            k += 1
        app = False
        if prev is not None and prev["b"] >= s["a"] - 1:
            pi = inks[prev["mid"]]
            ps = pi.sum()
            if ps > 0 and (pi & ink).sum() / ps > 0.85 and ink.sum() > ps * 1.04:
                app = True
        res.append({"t0": round(s["a"] / fps, 3), "t1": round(s["b"] / fps, 3), "n": s["b"] - s["a"],
                    "lines_y": [[int(a * 2 + y0), int(b * 2 + y0)] for a, b in lines], "ink_x": lx, "hex": hexv,
                    "first_frac": round(cnt[s['a']] / full, 2), "enter_fr": k, "append": app})
        prev = {"b": s["b"], "mid": mid}
    return res


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    mode = "color"
    if "--mode" in a:
        i = a.index("--mode")
        mode = a[i + 1]
        del a[i:i + 2]
    if len(a) < 4:
        print(__doc__)
        return 2
    mp4, y0, y1, out = a[0], int(a[1]), int(a[2]), a[3]
    res = capseg(mp4, y0, y1, mode=mode)
    if mode == "box":
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(len(res), "덩어리")
        return 0
    json.dump(res, open(out, "w"), indent=0)
    for r in res:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
