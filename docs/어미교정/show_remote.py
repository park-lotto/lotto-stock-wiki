# -*- coding: utf-8 -*-
"""받아온 서버 대본 요약 — 몇 개인지, 최근 5개 전문, 어미 버킷 상황."""
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

P = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad\remote_scripts.json"
d = json.load(open(P, encoding="utf-8"))

for k in ("mix_err", "wiki_err", "endings_err"):
    if k in d:
        print(f"[{k}] {d[k]}")

print(f"[믹스 대본] {len(d.get('mix', []))}개")
print(f"[위키 담은 대본] {len(d.get('wiki', []))}개")
print(f"[어미 부품] {len(d.get('endings', []))}개")

print("\n" + "=" * 70 + "\n최근 우리 대본 5개 (before 샘플)\n" + "=" * 70)
for m in d.get("mix", [])[:5]:
    full = " ".join(b["narration"] for b in m["beats"])
    print(f"\n[{m['job_id']}] 비트{len(m['beats'])} / {len(full)}자")
    for b in m["beats"]:
        print(f"  ({b['role']}) {b['narration']}")

print("\n" + "=" * 70 + "\n어미 부품은행\n" + "=" * 70)
for e in d.get("endings", [])[:60]:
    print(f"  {e['text']}  (freq={e['freq']}, {e['status']})")
