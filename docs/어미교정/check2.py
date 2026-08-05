# -*- coding: utf-8 -*-
"""2차 교정 검증 — 1차 대비 쏠림이 실제로 풀렸나(주장 아닌 실측)."""
import io
import json
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

S = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad"
p2 = json.load(open(S + r"\script_pairs2.json", encoding="utf-8"))

CLICHE = ["꿀템", "갓성비", "완벽 해결", "삶의 질", "필수템", "역대급"]
DEORA = re.compile(r"더라[고구]요")
WATCH = {"~것 같아요": "것 같아요", "~거 있죠": "거 있죠",
         "보내드릴게요": "보내드릴게요", "~더라고요류": None}


def stats(texts):
    c = {}
    for label, pat in WATCH.items():
        if pat is None:
            c[label] = sum(len(DEORA.findall(t)) for t in texts)
        else:
            c[label] = sum(t.count(pat) for t in texts)
    return c


a1 = [p["after1"] for p in p2]
a2 = [p["after2"] for p in p2]
s1, s2 = stats(a1), stats(a2)

print("[쏠림 표현 — 1차 → 2차 (40쌍 합계)]")
for k in WATCH:
    arrow = "OK" if s2[k] <= s1[k] else "악화"
    print(f"  {k:12} {s1[k]:3} → {s2[k]:3}   {arrow}")

# 규칙 위반 재검사
bad = {"deora": [], "watch": [], "cliche": [], "len": []}
ok = 0
for p in p2:
    a, b = p["after2"], p["before"].replace(" / ", " ")
    probs = []
    if len(DEORA.findall(a)) > 1:
        probs.append("더라고요"); bad["deora"].append(p["job_id"])
    if a.count("것 같아요") > 1 or a.count("거 있죠") > 1:
        probs.append("감시표현2회+"); bad["watch"].append(p["job_id"])
    hits = [c for c in CLICHE if c in a]
    if hits:
        probs.append("상투어"); bad["cliche"].append((p["job_id"], hits))
    r = len(a) / len(b) if b else 0
    if not (0.80 <= r <= 1.30):
        probs.append(f"길이{r:.2f}"); bad["len"].append((p["job_id"], round(r, 2)))
    if not probs:
        ok += 1

print(f"\n[전규칙 통과] 2차 {ok}/40쌍  (1차는 26/40이었다)")
print(f"  위반: 더라고요 {len(bad['deora'])} / 감시표현 {len(bad['watch'])} / "
      f"상투어 {len(bad['cliche'])} / 길이 {len(bad['len'])}")
if bad["cliche"]:
    print("   상투어:", bad["cliche"][:6])
if bad["len"]:
    print("   길이:", bad["len"][:10])

# CTA 다양성
print("\n[CTA 마지막 5글자 분포]")
cta = Counter()
for a in a2:
    last = [s for s in re.split(r"(?<=[.!?…])\s+", a) if s.strip()]
    if last:
        cta[last[-1].strip().rstrip(".!?…")[-6:]] += 1
for k, v in cta.most_common(12):
    print(f"  ...{k}: {v}")

print("\n[2차 종결 4글자 상위 15]")
surf = Counter()
for a in a2:
    for s in re.split(r"(?<=[.!?…])\s+", a):
        s = s.strip().rstrip(".!?…")
        if len(s) >= 3:
            surf[s[-4:]] += 1
for s, c in surf.most_common(15):
    print(f"  ...{s}: {c}")
print(f"\n[고유 종결형 수] 1차 대비: 2차 {len(surf)}종")
