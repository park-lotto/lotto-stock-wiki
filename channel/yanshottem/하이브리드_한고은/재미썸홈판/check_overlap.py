# -*- coding: utf-8 -*-
"""B13 같은 장면 중복 — 앞(얜샷템)+뒤(재미썸홈) 전 컷의 (소스, 구간)에서 겹치거나 ±3초 안 재사용을 센다.
예외 하나: 영상에서 바로 이웃한 두 컷이 같은 소스를 시간 앞으로 이어 갈 때(원본 컷 경계를 따라 다음 샷 — 되감김 아님, check_seams 로 따로 잼).
    PYTHONUTF8=1 py channel/yanshottem/하이브리드_한고은/재미썸홈판/check_overlap.py
"""
import importlib.util
import json
import sys
from pathlib import Path

R = Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/재미썸홈판/render")
D = Path(__file__).resolve().parent
GAP = 3.0
spec = importlib.util.spec_from_file_location("md", D.parent / "재료" / "make_derived.py")   # 2판 조각 → 원본 구간
md = importlib.util.module_from_spec(spec); spec.loader.exec_module(md)
DNAME = {"dA": "d_A.mp4", "dB": "d_B.mp4", "dGH": "d_GH.mp4#jae", "dI": "d_I.mp4", "dFR": "d_FR.mp4#jae"}
rows = []   # (영상 순번, 소스, 시작, 끝, 영상 시각)
fr = json.loads((D / "재료_render.json").read_text(encoding="utf-8"))["shots"][0]["cuts"]
t = 0.0
for c in fr:
    rows.append((len(rows), "hg", c["ss"], round(c["ss"] + c["dur"], 2), round(t, 2))); t += c["dur"]
seam = t
for g in json.loads((R / "back_timeline.json").read_text(encoding="utf-8"))["groups"]:
    if g["src"] in DNAME:   # 조각: 그 대목 원본 구간 전체로 센다
        w_ = md.orig_windows(DNAME[g["src"]])
        rows.append((len(rows), "hg", w_[0][0], w_[-1][1], round(seam + g["t0"], 2)))
        continue
    src = "hg" if g["src"] == "hg" else g["src"]
    rows.append((len(rows), src, g["ss"], round(g["ss"] + g["dur"], 2), round(seam + g["t0"], 2)))
bad, ok_next = [], []
for i, a in enumerate(rows):
    for b in rows[i + 1:]:
        if a[1] != b[1] or a[1].startswith(("img:", "meme:")) and a[1] != b[1]:
            continue
        if a[2] - GAP < b[3] and b[2] - GAP < a[3]:
            run = rows[a[0]:b[0] + 1]   # 2판: 사이 컷이 전부 원본 한 대목을 앞으로만 이어 가는 한 줄기면 예외(끼움 없음)
            if all(y[1] == a[1] and y[2] >= x[3] - 0.05 and y[2] - x[3] < GAP for x, y in zip(run, run[1:])):
                ok_next.append((a, b))
            else:
                bad.append((a, b))
for r in rows:
    print(f"#{r[0]:2d} {r[4]:6.2f}초  {r[1]:20s} {r[2]:7.2f}~{r[3]:7.2f}")
print("이웃 컷 앞으로 이어감(예외):", len(ok_next), [(a[2], b[2]) for a, b in ok_next])
print("겹침/±3초:", len(bad))
for a, b in bad:
    print("  ★", a, b)
sys.exit(1 if bad else 0)
