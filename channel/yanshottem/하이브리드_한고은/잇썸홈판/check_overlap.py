# -*- coding: utf-8 -*-
"""B13 같은 장면 중복 — 잇썸홈판 앞(얜샷템 4컷)+뒤(잇썸홈 컷) 전부를 **원본 시각**으로 되돌려 겹침·±3초 재사용을 센다(2판, 관제 097).
조각(d_*.mp4)은 재료/make_derived.py DERIVED 표로 원본 구간을 찾는다. 예외: 영상에서 연달아 붙은 컷들이 원본 한 대목을 시간 앞으로만 이어 갈 때(사이에 다른 컷 없음 — 되감김은 check_seams 로 따로 잼).
    PYTHONUTF8=1 py channel/yanshottem/하이브리드_한고은/잇썸홈판/check_overlap.py
"""
import importlib.util
import json
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
W = Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/잇썸홈판")
GAP = 3.0
spec = importlib.util.spec_from_file_location("md", D.parent / "재료" / "make_derived.py")
md = importlib.util.module_from_spec(spec); spec.loader.exec_module(md)

rows = []   # (순번, 원본 시작, 끝, 영상 시각, 이름)
fr = json.loads((W / "front" / "재료_front.json").read_text(encoding="utf-8"))["shots"][0]["cuts"]
t = 0.0
for c in fr:
    rows.append((len(rows), c["ss"], round(c["ss"] + c["dur"], 2), round(t, 2), c["src"])); t += c["dur"]
seam = t
for g in json.loads((W / "back" / "timeline.json").read_text(encoding="utf-8"))["groups"]:
    win = md.orig_windows(g["src"] + "#its") or md.orig_windows(g["src"])
    if win:   # 조각: 원본 구간 전체(늦춤 배수와 상관없이 그 대목 전체를 쓴 것으로 센다)
        a, b = win[0][0], win[-1][1]
    else:
        a, b = g["ss"], round(g["ss"] + g["dur"], 2)
    rows.append((len(rows), a, b, round(seam + g["t0"], 2), g["src"]))
bad, ok_next = [], []
for i, x in enumerate(rows):
    for y in rows[i + 1:]:
        if x[1] - GAP < y[2] and y[1] - GAP < x[2]:
            run = rows[x[0]:y[0] + 1]   # x~y 사이 컷이 전부 원본을 앞으로만 이어 가는 한 줄기면(다른 컷 끼움 없음) 같은 대목을 이어 쓴 것
            chain = all(b_[1] >= a_[2] - 0.05 and abs(b_[1] - a_[2]) < GAP for a_, b_ in zip(run, run[1:]))
            (ok_next if chain else bad).append((x, y))
for r in rows:
    print(f"#{r[0]:2d} {r[3]:6.2f}초  {r[4]:22s} 원본 {r[1]:7.2f}~{r[2]:7.2f}")
print("이웃 컷 앞으로 이어감(예외):", len(ok_next), [(a[1], b[1]) for a, b in ok_next])
print("겹침/±3초:", len(bad))
for a, b in bad:
    print("  ★", a, b)
sys.exit(1 if bad else 0)
