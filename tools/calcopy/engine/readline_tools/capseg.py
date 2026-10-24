# -*- coding: utf-8 -*-
"""자막 띠 분할(capseg) — 30fps 매 프레임 글자 잉크 마스크가 바뀌는 지점으로 자막 덩어리를 자른다. 글자 꼴마다 모드가 있다.

어디서 왔나(알고리즘은 각각 그대로 옮김):
  mode=color  06 잇템로그 워커 capseg.py(10-24) — '검정 외곽 옆 밝은 채움'(V>185 & 검정 V<45 9x9 팽창). 색·흰 채움 + 검정 외곽. 기본값.
  mode=bright/dark/both  06 썰풀다 워커 seg2.py(10-25) — bright = 흰 저채도 채움(V>200·S<70) + 검정 외곽, dark = 검정 글(V<60) 옆 흰,
              both = 둘 다. 마스크 2px 간격, 잉크 >80, yr 2px 단위.
  capseg_box  06 유머쇼쇼 워커 seg2.py·seg3.py(10-25, seg3 = --grid 줄 칸 거르기) — 흰 상자 위 검정 글(외곽 없음): 흰 행(흰 비율>0.45) ±7행 안 어두운 픽셀 = 잉크,
              IoU 차>0.35 또는 잉크가 10%·60칸 넘게 늘면(한 줄씩 덧붙는 자막) 새 덩어리, 2프레임 이하 조각은 앞 덩어리에 붙임.
              출력 꼴이 다르다(lines_y·ink_x·first_frac·enter_fr·append).
  mode=shadow 06 샤크탱크 워커 fsseg.py(10-25) — 외곽선 없이 그림자·번짐만 있는 흰/형광 자막(오른쪽아래 +4px 가 70↓ 어두움). cols(팔레트 비율) 출력.
입력: mp4 · 띠 y0 y1 (예: 잇템로그 1150 1460) · [--mode color|bright|dark|both|box]
출력(json 목록): color/bright/dark/both → [{t0, t1, n, ink, hex, yr}] · box → [{t0, t1, n, lines_y, ink_x, hex, first_frac, enter_fr, append}]
crop 은 exact=1 — yuv420 원본은 홀수 y·높이를 ffmpeg 가 짝수로 내려 잘라 프레임 크기가 어긋나고 reshape 가 프레임을 밀어 쓰레기가 된다
(10-25 실측: 띠 1137~1462(높이 325) → 실제 324줄 → 경계 39개 중 20개 어긋남). 짝수 띠는 exact 유무와 출력이 같다.

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/capseg.py <mp4> <y0> <y1> <out.json> [--mode color] [--grid 줄위끝y,...(box 만)]
"""
from __future__ import annotations

import json
import subprocess
import sys

import cv2
import numpy as np

MODES = ("color", "bright", "dark", "both", "box", "shadow")


def _diff(a, b):
    u = (a | b).sum()
    return 0 if u == 0 else 1 - (a & b).sum() / u


def src_fps(mp4: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", mp4],
                       capture_output=True, text=True).stdout.strip()
    try:
        a, b = (r.split("/") + ["1"])[:2]
        return float(a) / float(b)
    except (ValueError, ZeroDivisionError):
        return 0.0


def fps_filter(mp4: str, fps: float = 30.0) -> str:
    """원본이 fps 와 1 넘게 다르면(60fps 등) 'fps=30,' 을 앞에 붙인다 — 도구들은 프레임 번호÷30 으로 시각을 낸다.
    (06 꿀템노트 10-25: 60fps 원본을 그대로 넣으면 시각 2배·중복 프레임을 컷으로 셈 — m0Ex 72컷 vs 30fps 사본 18컷.) 30fps 원본은 그대로(재현 유지)."""
    f = src_fps(mp4)
    return f"fps={fps:g}," if f and abs(f - fps) > 1 else ""


def read_band(mp4: str, y0: int, y1: int, width: int = 1080, pix: str = "bgr24", scale: tuple | None = None) -> np.ndarray:
    H = y1 - y0
    vf = fps_filter(mp4) + f"crop={width}:{H}:0:{y0}:exact=1" + (f",scale={scale[0]}:{scale[1]}" if scale else "")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", vf, "-f", "rawvideo", "-pix_fmt", pix, "-"], capture_output=True).stdout
    w, h = scale if scale else (width, H)
    n = len(raw) // (w * h * 3)
    return np.frombuffer(raw, np.uint8)[:n * w * h * 3].reshape(n, h, w, 3)


def capseg(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080, mode: str = "color", frames: np.ndarray | None = None,
           grid: list[int] | None = None) -> list[dict]:
    """frames 를 주면(이미 자른 띠 [n,H,W,3] bgr) 읽기를 건너뛴다 — 띠 찾기·시험용. grid 는 box 모드에서만."""
    if mode == "box":
        return capseg_box(mp4, y0, y1, fps=fps, width=width, grid=grid)
    if mode == "shadow":
        return capseg_shadow(mp4, y0, y1, fps=fps, width=width)
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


SHADOW_PAL = {"흰": (253, 250, 250), "노랑": (252, 226, 61), "주황": (245, 155, 72), "빨강": (235, 78, 79), "초록": (66, 252, 81),
              "민트": (64, 248, 240), "파랑": (67, 165, 246), "분홍": (242, 98, 146)}   # 샤크탱크(해외쇼츠) 자막 팔레트(fsseg.py)


def shadow_mask(a: np.ndarray):
    """외곽선 없는 자막(그림자·번짐): 흰(min>225) 또는 형광(max>215·채도>110) 채움 중 오른쪽아래(+4,+4)가 70 넘게 어두운 픽셀, 3x3 팽창. a = RGB."""
    a = a.astype(int)
    mx, mn = a.max(2), a.min(2)
    br = (mn > 225) | ((mx > 215) & (mx - mn > 110))
    v = mx
    sh = np.zeros_like(v)
    sh[:-4, :-4] = v[4:, 4:]
    m = br & (sh < v - 70)
    return cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0, br


def capseg_shadow(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080, palette: dict | None = None) -> list[dict]:
    """06 샤크탱크 워커 fsseg.py(10-25) 덩어리 분할 그대로: 마스크 IoU 차>0.5 & 잉크>40 이면 경계, 2프레임 이하 덩어리(넘김 가로흐림)는 뒤에 붙임.
    출력 = [{t0,t1,n,ink(덩어리 중앙값),yr,cols(팔레트 비율),hex:None}]."""
    PAL = palette or SHADOW_PAL
    PN = list(PAL)
    PV = np.array([PAL[k] for k in PN], float)
    F = read_band(mp4, y0, y1, width, pix="rgb24")
    H = y1 - y0
    M, C, Y = [], [], []
    for a in F:
        m, br = shadow_mask(a)
        M.append(cv2.resize(m.astype(np.uint8) * 255, (270, max(1, H // 4)), interpolation=cv2.INTER_AREA) > 40)
        full = br & cv2.dilate(m.astype(np.uint8), np.ones((15, 15), np.uint8)).astype(bool)
        px = a[full]
        if len(px) > 300:
            d = ((px[:, None, :].astype(float) - PV[None]) ** 2).sum(2)
            k = d.argmin(1)
            ok = d.min(1) < 60 ** 2
            cnt = {PN[i]: int(((k == i) & ok).sum()) for i in range(len(PN))}
        else:
            cnt = {}
        C.append(cnt)
        rows = np.where(m.sum(1) > 8)[0]
        Y.append([int(y0 + rows.min()), int(y0 + rows.max())] if len(rows) else None)
    n = len(M)
    ink = [int(x.sum()) for x in M]
    cuts = [0]
    for i in range(1, n):
        if _diff(M[i], M[i - 1]) > 0.5 and (ink[i] > 40 or ink[i - 1] > 40):
            cuts.append(i)
    cuts.append(n)
    out = []
    for s in ([a, b] for a, b in zip(cuts[:-1], cuts[1:])):
        if out and s[1] - s[0] <= 2:
            out.append(s)
            continue
        if out and out[-1][1] - out[-1][0] <= 2:
            s = [out[-1][0], s[1]]
            out[-1] = s
            continue
        out.append(s)
    res = []
    for a, b in out:
        lo = a + min(3, (b - a) // 3)
        mid = (lo + b) // 2
        tot = {}
        for c in C[lo:b]:
            for k, v in c.items():
                tot[k] = tot.get(k, 0) + v
        tt = sum(tot.values()) or 1
        cols = {k: round(v / tt, 2) for k, v in sorted(tot.items(), key=lambda x: -x[1]) if v / tt >= 0.04}
        res.append({"t0": round(a / fps, 3), "t1": round(b / fps, 3), "n": b - a, "ink": int(np.median(ink[lo:b])) if b > lo else ink[a],
                    "yr": Y[mid], "cols": cols, "hex": None})
    return res


def capseg_box(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080, grid: list[int] | None = None) -> list[dict]:
    """grid = 자막 줄 위끝 y 목록(유머쇼쇼 seg3.py): 주면 그 줄 칸(−6~+58px)에 잉크가 줄 머리부터 있고 바로 아래로 이어지지 않을 때만 남긴다
    (창 그림 속 검정 글자가 상자 자막으로 섞이는 것을 막는다)."""
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
        if grid:
            keep = np.zeros(H, bool)
            for g in grid:
                a = max((g - 6 - y0) // 2, 0)
                b = min((g + 58 - y0) // 2, H)
                rs = ink[a:b].sum(1) > 0
                below = ink[b:b + 3].sum(1) > 0 if b + 3 <= H else np.zeros(1, bool)
                if rs.any() and rs[:8].any() and not below.all():
                    keep[a:b] = True
            ink = ink & keep[:, None]
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
    grid = None
    if "--grid" in a:
        i = a.index("--grid")
        grid = [int(g) for g in a[i + 1].split(",")]
        del a[i:i + 2]
    if "--mode" in a:
        i = a.index("--mode")
        mode = a[i + 1]
        del a[i:i + 2]
    if len(a) < 4:
        print(__doc__)
        return 2
    mp4, y0, y1, out = a[0], int(a[1]), int(a[2]), a[3]
    res = capseg(mp4, y0, y1, mode=mode, grid=grid)
    if mode in ("box", "shadow"):
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(len(res), "덩어리")
        return 0
    json.dump(res, open(out, "w"), indent=0)
    for r in res:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
