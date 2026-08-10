# -*- coding: utf-8 -*-
"""3차 결과 40개 전부 — 교정본만 읽기 좋게. 규칙위반은 표시."""
import io
import json
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

S = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad"
p3 = json.load(open(S + r"\script_pairs3.json", encoding="utf-8"))

CLICHE = ["꿀템", "갓성비", "완벽 해결", "삶의 질", "필수템", "역대급"]
DEORA = re.compile(r"더라[고구]요")

for i, p in enumerate(p3, 1):
    a, b = p["after3"], p["before"].replace(" / ", " ")
    r = len(a) / len(b) if b else 0
    flags = []
    if len(DEORA.findall(a)) > 1:
        flags.append("더라고요2회+")
    if any(c in a for c in CLICHE):
        flags.append("상투어")
    if not (0.80 <= r <= 1.30):
        flags.append(f"길이{r:.2f}배")
    mark = ("  ⚠ " + ", ".join(flags)) if flags else "  OK"
    print(f"\n{'─' * 74}")
    print(f"{i:2}. [{p['job_id']}]{mark}   ({len(a)}자)")
    print(f"{'─' * 74}")
    for s in re.split(r"(?<=[.!?…])\s+", a):
        if s.strip():
            print(f"  {s.strip()}")
