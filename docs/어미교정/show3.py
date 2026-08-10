# -*- coding: utf-8 -*-
"""3차 결과 — 사장님이 지적한 대본(1번·3번) 우선 + 규칙 통과분."""
import io
import json
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

S = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad"
p3 = json.load(open(S + r"\script_pairs3.json", encoding="utf-8"))
by = {p["job_id"]: p for p in p3}

# 사장님이 직접 언급한 두 개를 먼저
PICK = ["bb9db3a5f759", "6faf8fb53755"]
rest = [p for p in p3 if p["job_id"] not in PICK]

CLICHE = ["꿀템", "갓성비", "완벽 해결", "삶의 질", "필수템", "역대급"]
DEORA = re.compile(r"더라[고구]요")
clean = []
for p in rest:
    a, b = p["after3"], p["before"].replace(" / ", " ")
    r = len(a) / len(b) if b else 0
    if len(DEORA.findall(a)) > 1 or any(c in a for c in CLICHE):
        continue
    if not (0.80 <= r <= 1.30):
        continue
    clean.append(p)

show = [by[k] for k in PICK if k in by] + clean[:3]

for i, p in enumerate(show, 1):
    tag = " ★사장님이 지적한 대본" if p["job_id"] in PICK else ""
    print("=" * 74)
    print(f"■ {i}번 [{p['job_id']}]{tag}")
    print("=" * 74)
    print("\n[2차 — 사장님이 보신 것]")
    for s in re.split(r"(?<=[.!?…])\s+", p["after2"]):
        if s.strip():
            print(f"   {s.strip()}")
    print("\n[3차 — 피드백 반영]")
    for s in re.split(r"(?<=[.!?…])\s+", p["after3"]):
        if s.strip():
            print(f"   {s.strip()}")
    print(f"\n   쓴 기법: {', '.join(p.get('techniques', []))}")
    print(f"   바꾼 것: {p.get('changed','')}")
    print()
