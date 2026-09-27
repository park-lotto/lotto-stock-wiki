# -*- coding: utf-8 -*-
"""자막 글자의 **모양** 실측 — 굵기(획 폭)·글자 높이·외곽선·그림자·등장 효과.
표본 폴더에서: PYTHONUTF8=1 py ../measure/glyph_style.py [편당 자막 수=6] → glyph.json + 콘솔

재는 법(외부 기준표 1-02·1-09·1-11·1-33 정의를 그대로 구현):
- 잉크 = 자막 띠(y1272~1470) 안 밝기<120 화소. 획 폭 = 잉크 가로/세로 연속 길이(30px 미만)의 중앙값 중 작은 쪽.
- 글자 높이 = 첫 줄 잉크 bbox 높이(줄은 행 잉크 밀도로 가른다).
- 외곽선 = 잉크를 3px 팽창한 고리의 평균색이 배경(248)·잉크 둘 다와 40 이상 다르면 "있음".
- 그림자 = 잉크를 (dx,dy)=2~6px 옮긴 자리 중 잉크가 아닌데 어두운(<180) 비율이 30% 넘는 오프셋.
- 등장 효과 = 자막 시작 시각 뒤 0~8프레임(30fps) 잉크 bbox 폭·중심·면적 변화. 폭 5%↑=확대, 중심 5px↑=이동, 면적이 늘면=페이드/타자기, 아니면 없음.
"""
import subprocess, json, sys, glob, statistics as st
import numpy as np

BAND_Y, BAND_H = 1278, 194     # 1272로 잡으면 슬롯 마지막 행(1273)이 섞여 줄 높이가 1px로 나온다(2026-09-28 실측 6/9편)
PER = int(sys.argv[1]) if len(sys.argv) > 1 else 6
cuts = json.load(open("cuts.json", encoding="utf-8"))


def frame(f, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", f, "-frames:v", "1",
                          "-vf", f"crop=1080:{BAND_H}:0:{BAND_Y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    if len(raw) < 1080 * BAND_H * 3:
        return None
    return np.frombuffer(raw, np.uint8).reshape(BAND_H, 1080, 3)


def runs(mask, axis):
    m = mask if axis == 0 else mask.T
    out = []
    for row in m:
        n = 0
        for v in row:
            if v: n += 1
            elif n: out.append(n); n = 0
        if n: out.append(n)
    out = [x for x in out if x < 30]
    return st.median(out) if out else None


def ink_box(mask):
    ys, xs = np.where(mask)
    if len(ys) < 50:
        return None
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max()), int(mask.sum())


def measure(img):
    lum = img.mean(axis=2)
    ink = lum < 120
    box = ink_box(ink)
    if not box:
        return None
    # 첫 줄 높이: 행 잉크 밀도가 있는 첫 덩어리
    rows = ink.sum(axis=1) > 3
    # 첫 줄 = 잉크 행이 10행 이상 이어지는 첫 덩어리(1~2행짜리 티끌은 건너뛴다)
    y0 = y1 = None; i = 0
    while i < BAND_H:
        if rows[i]:
            j = i
            while j < BAND_H - 1 and rows[j + 1]: j += 1
            if j - i + 1 >= 10: y0, y1 = i, j; break
            i = j + 1
        else:
            i += 1
    if y0 is None:
        return None
    line_h = y1 - y0 + 1
    sw = [x for x in (runs(ink[y0:y1 + 1], 0), runs(ink[y0:y1 + 1], 1)) if x]
    stroke = min(sw) if sw else None
    # 외곽선: 3px 고리
    import cv2
    ring = cv2.dilate(ink.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool) & ~ink
    ring_rgb = img[ring].mean(axis=0) if ring.any() else None
    outline = bool(ring_rgb is not None and abs(ring_rgb.mean() - 248) > 40 and abs(ring_rgb.mean() - lum[ink].mean()) > 40)
    # 그림자
    shadow = None
    darkish = (lum < 180) & ~ink
    for dy in range(2, 7):
        for dx in range(-6, 7, 2):
            sh = np.roll(np.roll(ink, dy, 0), dx, 1) & ~ink
            if sh.sum() and (darkish & sh).sum() / sh.sum() > 0.3:
                shadow = (dx, dy); break
        if shadow: break
    return {"line_h": line_h, "stroke": stroke, "outline": outline, "ring_rgb": [int(v) for v in ring_rgb] if ring_rgb is not None else None,
            "shadow": shadow, "box": box}


def anim(f, t0):
    seq = []
    for k in range(0, 9):
        img = frame(f, t0 + k / 30)
        if img is None: continue
        b = ink_box(img.mean(axis=2) < 120)
        seq.append(b)
    seq = [b for b in seq if b]
    if len(seq) < 4:
        return "판정불가"
    w = [b[1] - b[0] for b in seq]; cx = [(b[0] + b[1]) / 2 for b in seq]; area = [b[4] for b in seq]
    if abs(w[-1] - w[0]) / max(w[-1], 1) > 0.05: return "확대/축소"
    if abs(cx[-1] - cx[0]) > 5: return "이동"
    if area[0] < 0.5 * area[-1]: return "페이드/타자기"
    return "없음"


out = {}
for f in sorted(glob.glob("*.mp4")):
    if f + "" not in cuts: continue
    c = cuts[f]; ts = [0] + c["sub_times"]; ends = c["sub_times"] + [c["dur"]]
    idx = np.linspace(0, len(ts) - 1, min(PER, len(ts))).astype(int)
    ms, an = [], []
    for i in idx:
        img = frame(f, (ts[i] + ends[i]) / 2)
        m = measure(img) if img is not None else None
        if m: ms.append(m)
        an.append(anim(f, ts[i] + 0.03))
    if not ms: continue
    out[f[:11]] = {"line_h": st.median([m["line_h"] for m in ms]), "stroke": st.median([m["stroke"] for m in ms if m["stroke"]]),
                   "outline": sum(m["outline"] for m in ms), "shadow": sum(1 for m in ms if m["shadow"]), "n": len(ms),
                   "anim": {a: an.count(a) for a in set(an)}, "ring_rgb": ms[0]["ring_rgb"]}
    print(f[:11], out[f[:11]])
json.dump(out, open("glyph.json", "w"), ensure_ascii=False, indent=1)
if out:
    print("\n줄 높이 중앙", st.median([v["line_h"] for v in out.values()]), "획 폭 중앙", st.median([v["stroke"] for v in out.values()]),
          "외곽선 있음", sum(v["outline"] for v in out.values()), "/", sum(v["n"] for v in out.values()),
          "그림자", sum(v["shadow"] for v in out.values()))
