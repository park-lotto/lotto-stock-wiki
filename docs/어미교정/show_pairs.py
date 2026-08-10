# -*- coding: utf-8 -*-
"""전 규칙 통과한 쌍만 골라 before/after를 나란히 보여준다."""
import io
import json
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

P = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad\script_pairs.json"
pairs = json.load(open(P, encoding="utf-8"))

CLICHE = ["꿀템", "갓성비", "완벽 해결", "삶의 질", "필수템", "역대급"]
DEORA = re.compile(r"더라[고구]요")

clean = []
for p in pairs:
    a = p["after"]
    blen = len(p["before"].replace(" / ", " "))
    ratio = len(a) / blen if blen else 0
    if len(DEORA.findall(a)) > 1:
        continue
    if any(c in a for c in CLICHE):
        continue
    if not (0.80 <= ratio <= 1.30):
        continue
    clean.append(p)

n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
print(f"[통과 {len(clean)}쌍 중 {min(n, len(clean))}개]\n")
for p in clean[:n]:
    print("=" * 72)
    print(f"[{p['job_id']}]  진단: {p['diagnosis']}")
    print("-" * 72)
    print("BEFORE (우리 것):")
    for s in p["before"].split(" / "):
        print(f"   {s}")
    print("\nAFTER (교정):")
    print(f"   {p['after']}")
    print(f"\n   어미흐름: {' → '.join(p['ending_map'])}")
    print()
