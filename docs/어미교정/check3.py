# -*- coding: utf-8 -*-
"""3차 검증 — 사장님 지적 4개가 실제로 반영됐나(주장 아닌 실측)."""
import io
import json
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

S = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad"
p3 = json.load(open(S + r"\script_pairs3.json", encoding="utf-8"))

CLICHE = ["꿀템", "갓성비", "완벽 해결", "삶의 질", "필수템", "역대급"]
DEORA = re.compile(r"더라[고구]요")
# 감탄 마무리(장점묶음) 흔적
GAMTAN = re.compile(r"놀랍|대단|이 정도면|와~|못 지울|없겠|겠는데요|겠더라")
# 화면 지목
JIMOK = re.compile(r"보세요|보이시죠|보이세요|보시면|이거 보|저것 좀")
# 명사끊기 CTA
MYEONGSA = re.compile(r"(이것|이 제품|그 비결|이 방법|바로 이것)\s*[!?]")

print("=" * 60)
print("사장님 지적 4개 반영 실측")
print("=" * 60)

a2 = [p["after2"] for p in p3]
a3 = [p["after3"] for p in p3]


def cnt(texts, pat):
    if isinstance(pat, str):
        return sum(t.count(pat) for t in texts)
    return sum(len(pat.findall(t)) for t in texts)


rows = [
    ("④ '글쎄' 문미(제거대상)", ", 글쎄", "적을수록 좋음"),
    ("★더라고요 계열(최대1/대본)", DEORA, "적을수록 좋음"),
    ("① 장점묶음 감탄", GAMTAN, "많을수록 좋음"),
    ("③ 화면 지목", JIMOK, "많을수록 좋음"),
    ("② 명사끊기 CTA", MYEONGSA, "몇 개만"),
]
for label, pat, note in rows:
    print(f"  {label:28} 2차 {cnt(a2, pat):3} → 3차 {cnt(a3, pat):3}   ({note})")

# 대본당 위반
bad = Counter()
ok = 0
detail = {"len": [], "deora": [], "cliche": []}
for p in p3:
    a, b = p["after3"], p["before"].replace(" / ", " ")
    probs = []
    if len(DEORA.findall(a)) > 1:
        probs.append("더라고요"); detail["deora"].append(p["job_id"])
    if a.count("것 같아요") > 1 or a.count("거 있죠") > 1:
        probs.append("감시표현")
    if ", 글쎄" in a:
        probs.append("글쎄")
    h = [c for c in CLICHE if c in a]
    if h:
        probs.append("상투어"); detail["cliche"].append((p["job_id"], h))
    r = len(a) / len(b) if b else 0
    if not (0.80 <= r <= 1.30):
        probs.append("길이"); detail["len"].append((p["job_id"], round(r, 2)))
    for x in probs:
        bad[x] += 1
    if not probs:
        ok += 1

print(f"\n[전규칙 통과] 3차 {ok}/40  (1차 26 / 2차 24)")
print(f"  위반내역: {dict(bad)}")
if detail["len"]:
    print(f"  길이이탈: {detail['len'][:10]}")
if detail["cliche"]:
    print(f"  상투어: {detail['cliche'][:6]}")

# 기법 자기보고
tech = Counter()
for p in p3:
    for t in p.get("techniques", []):
        tech[t] += 1
print("\n[모델 자기보고 기법 분포]")
for t, c in tech.most_common():
    print(f"  {t}: {c}")

print("\n[3차 종결 4글자 상위 12]")
surf = Counter()
for a in a3:
    for s in re.split(r"(?<=[.!?…])\s+", a):
        s = s.strip().rstrip(".!?…")
        if len(s) >= 3:
            surf[s[-4:]] += 1
for s, c in surf.most_common(12):
    print(f"  ...{s}: {c}")
print(f"[고유 종결형] 3차 {len(surf)}종 (2차 96종)")
