# -*- coding: utf-8 -*-
"""생성된 40쌍이 규칙을 실제로 지켰는지 기계적으로 검증한다(주장 아닌 실측)."""
import io
import json
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

P = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad\script_pairs.json"
pairs = json.load(open(P, encoding="utf-8"))

CLICHE = ["꿀템", "갓성비", "완벽 해결", "삶의 질", "필수템", "역대급"]
DEORA = re.compile(r"더라[고구]요")

bad_deora, bad_cliche, bad_len, ok = [], [], [], 0
before_deora_total = after_deora_total = 0
ending_funcs = Counter()

for p in pairs:
    b, a = p["before"], p["after"]
    nb, na = len(DEORA.findall(b)), len(DEORA.findall(a))
    before_deora_total += nb
    after_deora_total += na
    problems = []
    if na > 1:
        problems.append(f"더라고요 {na}회")
        bad_deora.append((p["job_id"], na))
    hits = [c for c in CLICHE if c in a]
    if hits:
        problems.append("상투어 " + ",".join(hits))
        bad_cliche.append((p["job_id"], hits))
    # before는 ' / ' 구분자가 들어있어 길이 비교 시 제거
    blen = len(b.replace(" / ", " "))
    ratio = len(a) / blen if blen else 0
    if not (0.80 <= ratio <= 1.30):
        problems.append(f"길이 {ratio:.2f}배")
        bad_len.append((p["job_id"], round(ratio, 2)))
    if not problems:
        ok += 1
    for f in p.get("ending_map", []):
        ending_funcs[f] += 1

print(f"[총] {len(pairs)}쌍 / 전규칙 통과 {ok}쌍")
print(f"[~더라고요] before 총 {before_deora_total}회 → after 총 {after_deora_total}회")
print(f"[위반] 더라고요2회+ {len(bad_deora)} / 상투어 {len(bad_cliche)} / 길이이탈 {len(bad_len)}")
if bad_deora:
    print("   더라고요:", bad_deora[:8])
if bad_cliche:
    print("   상투어:", bad_cliche[:8])
if bad_len:
    print("   길이:", bad_len[:8])

print("\n[어미 기능 분포]")
for f, c in ending_funcs.most_common():
    print(f"  {f}: {c}")

# after 전체에서 실제 종결어미 표면형을 세어 단조로움을 재확인
surf = Counter()
for p in pairs:
    for s in re.split(r"(?<=[.!?…])\s+", p["after"]):
        s = s.strip().rstrip(".!?…")
        if len(s) >= 3:
            surf[s[-4:]] += 1
print("\n[after 종결 4글자 상위 15]")
for s, c in surf.most_common(15):
    print(f"  ...{s}: {c}")
