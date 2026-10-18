# -*- coding: utf-8 -*-
"""완성본 컷 목록에서 같은 소스의 겹치거나 ±3초 안 구간이 두 번 쓰였나(사장님 10-17 수정3 "장면 중복 금지").
    PYTHONUTF8=1 py channel/evenshopping/작품1_총알람/check_overlap.py <render 폴더>"""
import json
import sys
from pathlib import Path

GAP = 3.0
d = json.loads((Path(sys.argv[1]) / "timeline.json").read_text(encoding="utf-8"))
rows = [(g["src"], g["ss"], round(g["ss"] + (g.get("src_span") or g["dur"]), 2), g["t0"], g["pieces"]) for g in d["groups"]]
bad = []
for i, a in enumerate(rows):
    for b in rows[i + 1:]:
        if a[0] == b[0] and a[1] - GAP < b[2] and b[1] - GAP < a[2]:
            bad.append((a, b))
for r in sorted(rows):
    print(f"{r[0]:22s} {r[1]:7.2f}~{r[2]:7.2f}  (영상 {r[3]:.2f}초, 토막 {r[4]})")
print("겹침/±3초:", len(bad))
for a, b in bad:
    print("  ★", a, b)
sys.exit(1 if bad else 0)
