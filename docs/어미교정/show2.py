# -*- coding: utf-8 -*-
"""2차 교정 결과를 사장님이 읽고 고를 수 있게 보여준다.
규칙 전부 통과한 것 우선, 원본(before)과 나란히.
"""
import io
import json
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

S = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad"
pairs = json.load(open(S + r"\script_pairs2.json", encoding="utf-8"))

CLICHE = ["꿀템", "갓성비", "완벽 해결", "삶의 질", "필수템", "역대급"]
DEORA = re.compile(r"더라[고구]요")

clean = []
for p in pairs:
    a, b = p["after2"], p["before"].replace(" / ", " ")
    r = len(a) / len(b) if b else 0
    if len(DEORA.findall(a)) > 1:
        continue
    if any(c in a for c in CLICHE):
        continue
    if not (0.80 <= r <= 1.30):
        continue
    clean.append(p)

n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
print(f"규칙 통과 {len(clean)}쌍 중 {min(n, len(clean))}개\n")
for i, p in enumerate(clean[:n], 1):
    print("=" * 74)
    print(f"■ {i}번  [{p['job_id']}]")
    print("=" * 74)
    print("\n[지금 우리 대본 — 문제]")
    for s in p["before"].split(" / "):
        print(f"   {s}")
    print("\n[교정본 — 이걸 읽어보세요]")
    # 문장 단위로 줄바꿈해 읽기 쉽게
    for s in re.split(r"(?<=[.!?…])\s+", p["after2"]):
        if s.strip():
            print(f"   {s.strip()}")
    print(f"\n   (어미흐름: {' → '.join(p['ending_map2'])})")
    print()
