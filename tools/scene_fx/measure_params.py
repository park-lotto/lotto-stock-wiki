# -*- coding: utf-8 -*-
"""눈 분류로 찾은 레퍼런스 효과의 '값'을 프레임에서 정밀하게 잰다 (관제 124) — 팩 기본값의 근거.

- jump_zoom_cut : 컷 앞뒤 프레임 특징점 닮음변환 배율(눈대중 대신)
- dissolve      : 앞 장면→뒤 장면 섞임이 이어진 시간(앞뒤 대비 섞임 정도로)
- dark          : 화면 밝기가 앞뒤 대비 몇 %로 떨어지고 몇 초 이어지나 (어두운 제목 칸·어둡게 덮기)
- slow_zoom     : 훅 천천히 확대의 시간별 누적 배율

사용: py tools/scene_fx/measure_params.py --dir <영상폴더> --summary <eye_summary.json> --out <params.json>
"""
import argparse, json, os, statistics, sys
import numpy as np
import cv2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench  # noqa: E402

# 라벨 밖 연출(서브에이전트 보고에서 시각을 받은 것 — 2026-10-05 눈 분류 B0·B3·B6·B1·B4)
DARK_TITLE = ["vzGxDD0TSAQ", "XCfFzX6k9TA", "XgT4o7IlNV8", "HnawqPcNDss", "Hg9Gq-l129c", "fvegwp_lXak",
              "Kra1xml8590", "-RApcT0qrps", "3tUbexOTpZY", "Apoc8-5-wCA", "dLxAo-s6ZPc", "qqkqMaNL8Ds"]
DARK_OVER = [("04vmSG5Isy4", 1.97), ("3tUbexOTpZY", 5.07), ("khPKdPDDo_0", 7.47), ("khPKdPDDo_0", 23.77),
             ("khPKdPDDo_0", 30.8), ("xLqzgM_l6Eo", 11.71), ("xLqzgM_l6Eo", 27.16)]
SLOW = [("kTf3rBERh30", 0.0, 1.9), ("-pWrm2DhOhs", 0.0, 1.5)]


def frames_at(path, t0, t1):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0, t0) * 1000)
    out = []
    while True:
        pos = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        ok, f = cap.read()
        if not ok or pos > t1:
            break
        out.append((pos, f))
    cap.release()
    return out, fps


def region_of(path):
    fr, _ = bench.read_frames(path)
    y0, y1, x0, x1 = bench.video_region(fr)
    return y0 / bench.H, y1 / bench.H, x0 / bench.W, x1 / bench.W


def crop(f, reg):
    h, w = f.shape[:2]
    y0, y1, x0, x1 = reg
    return f[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]


def gray(f):
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (270, int(270 * g.shape[0] / g.shape[1])))


def jump_zoom(path, t, reg):
    fr, fps = frames_at(path, t - 0.25, t + 0.25)
    best = None
    for i in range(1, len(fr)):
        a, b = gray(crop(fr[i - 1][1], reg)), gray(crop(fr[i][1], reg))
        d = float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean())
        if best is None or d > best[0]:
            best = (d, a, b)
    if not best:
        return None
    m = bench.affine(best[1], best[2])
    if not m or m["n"] < 20 or m["inl"] < 0.3:
        return None
    return round(m["s"], 3)


def luma_series(path, t0, t1, reg):
    fr, fps = frames_at(path, t0, t1)
    return [(p, float(cv2.cvtColor(crop(f, reg), cv2.COLOR_BGR2GRAY).mean())) for p, f in fr]


def dark_event(path, t, reg, look=2.5):
    """t 근처에서 밝기가 떨어진 구간: 기준(앞뒤 밝은 쪽 중앙값) 대비 최저 비율, 기준의 80% 아래로 머문 시간."""
    s = luma_series(path, max(0, t - look), t + look, reg)
    if len(s) < 10:
        return None
    vals = np.array([v for _, v in s])
    base = float(np.percentile(vals, 80))
    low = vals < 0.8 * base
    if not low.any():
        return None
    k = int(np.argmin(vals))
    i0 = k
    while i0 > 0 and low[i0 - 1]:
        i0 -= 1
    i1 = k
    while i1 < len(vals) - 1 and low[i1 + 1]:
        i1 += 1
    return {"min_ratio": round(float(vals[k]) / base, 2), "dur": round(s[i1][0] - s[i0][0], 2), "at": round(s[i0][0], 2)}


def slow_zoom(path, t0, t1, reg):
    fr, fps = frames_at(path, t0, t1)
    acc, curve = 1.0, []
    for i in range(1, len(fr)):
        m = bench.affine(gray(crop(fr[i - 1][1], reg)), gray(crop(fr[i][1], reg)))
        if m and m["inl"] >= 0.5:
            acc *= m["s"]
        curve.append((round(fr[i][0] - t0, 2), round(acc, 3)))
    return curve


def dissolve_len(path, t, reg):
    """t±0.4초에서 앞 장면(A)·뒤 장면(B) 사이 섞인 프레임이 이어진 시간."""
    fr, fps = frames_at(path, t - 0.4, t + 0.4)
    if len(fr) < 6:
        return None
    g = [gray(crop(f, reg)).astype(np.float32) for _, f in fr]
    A, B = g[0], g[-1]
    mixed = []
    for x in g:
        da, db = float(np.abs(x - A).mean()), float(np.abs(x - B).mean())
        mixed.append(min(da, db) > 0.25 * float(np.abs(A - B).mean()))
    n = sum(mixed)
    return round(n / fps, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    summ = json.load(open(a.summary, encoding="utf-8"))
    regs = {}

    def reg(v):
        if v not in regs:
            regs[v] = region_of(os.path.join(a.dir, v + ".mp4"))
        return regs[v]
    out = {"jump_zoom": [], "dissolve": [], "dark_title": [], "dark_over": [], "slow_zoom": []}
    for v in summ:
        p = os.path.join(a.dir, v["id"] + ".mp4")
        for x in v["items"]:
            if x["label"] == "jump_zoom_cut":
                s = jump_zoom(p, x["t"], reg(v["id"]))
                out["jump_zoom"].append({"id": v["id"], "t": x["t"], "eye": x.get("scale"), "measured": s,
                                         "zone": x["zone"]})
            elif x["label"] == "dissolve":
                out["dissolve"].append({"id": v["id"], "t": x["t"], "eye_frames": x.get("frames"),
                                        "sec": dissolve_len(p, x["t"], reg(v["id"]))})
    for vid in DARK_TITLE:
        e = dark_event(os.path.join(a.dir, vid + ".mp4"), 0.0, reg(vid), look=2.5)
        out["dark_title"].append({"id": vid, **(e or {"none": True})})
    for vid, t in DARK_OVER:
        e = dark_event(os.path.join(a.dir, vid + ".mp4"), t, reg(vid))
        out["dark_over"].append({"id": vid, "t": t, **(e or {"none": True})})
    for vid, t0, t1 in SLOW:
        out["slow_zoom"].append({"id": vid, "curve": slow_zoom(os.path.join(a.dir, vid + ".mp4"), t0, t1, reg(vid))})
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 요약
    js = [x["measured"] for x in out["jump_zoom"] if x["measured"]]
    zin = [s for s in js if s > 1.03]
    zout = [s for s in js if s < 0.97]
    print(f"점프 줌 컷 {len(out['jump_zoom'])}건 중 잰 것 {len(js)}: 확대 {len(zin)}건 중앙 {statistics.median(zin) if zin else '-'}"
          f" (사분위 {statistics.quantiles(zin, n=4) if len(zin) > 3 else zin}) · 축소 {len(zout)}건 중앙 {statistics.median(zout) if zout else '-'}"
          f" · 거의 1배 {len(js) - len(zin) - len(zout)}")
    ds = [x["sec"] for x in out["dissolve"] if x["sec"]]
    print(f"디졸브 {len(ds)}건 길이 중앙 {statistics.median(ds) if ds else '-'}초 범위 {min(ds) if ds else '-'}~{max(ds) if ds else '-'}")
    for k in ("dark_title", "dark_over"):
        ok = [x for x in out[k] if "min_ratio" in x]
        if ok:
            print(f"{k}: {len(ok)}/{len(out[k])}건 · 밝기 최저 비율 중앙 {statistics.median(x['min_ratio'] for x in ok)}"
                  f" · 이어진 시간 중앙 {statistics.median(x['dur'] for x in ok)}초 · 각각 {[(x['min_ratio'], x['dur']) for x in ok]}")
    for x in out["slow_zoom"]:
        c = x["curve"]
        print("slow_zoom", x["id"], "끝 배율", c[-1][1] if c else None, "중간점", c[len(c) // 2] if c else None)


if __name__ == "__main__":
    main()
