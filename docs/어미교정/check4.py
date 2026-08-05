# -*- coding: utf-8 -*-
"""4차 검증 — 4차 목표 결함 3개 + 길이가 실제로 잡혔나(주장 아닌 실측)."""
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
p4 = json.load(open(os.path.join(HERE, "script_pairs4.json"), encoding="utf-8"))

CLICHE = ["꿀템", "갓성비", "완벽 해결", "삶의 질", "필수템", "역대급"]
DEORA = re.compile(r"더라[고구]요")
MYEONGSA = re.compile(r"(이것|이 제품|그 비결|그 비법|이 방법|바로 이것)\s*[!?]")
JIMOK = re.compile(r"보세요|보이시죠|보이세요|보시면|이거 보|저거 보|여기 보|이 장면")
CTA_HINT = re.compile(r"댓글|남겨|팔로우|저장")


# 서술어 종결(…요/…다/…죠/…까/…네 등)로 끝나면 완결 문장, 아니면 명사끊기로 본다
_VERB_END = re.compile(r"(요|다|죠|까|네|게|래|지)\s*[!?.…]*$")


def cta_order_bad(text):
    """명사끊기(미완성) 문장이 CTA 문장 '뒤'에 오면 위반 (4차 결함 ①).

    고정 명사 목록이 아니라 '서술어로 안 끝나는 ! 문장'으로 일반 판정 —
    "…만들어 줄 이 스팀기!"가 목록 매칭에서 빠져 통과한 실사고(2026-08-05) 재발 방지.
    """
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    seen_cta = False
    for s in sents:
        if CTA_HINT.search(s):
            seen_cta = True
        elif seen_cta and s.endswith("!") and not _VERB_END.search(s.rstrip("!")):
            return True
    return False


a3 = [p["after3"] for p in p4]
a4 = [p["after4"] for p in p4]


def cnt(texts, pat):
    if isinstance(pat, str):
        return sum(t.count(pat) for t in texts)
    return sum(len(pat.findall(t)) for t in texts)


print("=" * 60)
print("4차 목표 결함 실측 (3차 → 4차)")
print("=" * 60)
rows = [
    ("① CTA뒤 명사끊기(위반건수)", None, "0이어야 함"),
    ("② 별표 * 포함 대본", "*", "0이어야 함"),
    ("③ '보이시죠' 횟수", "보이시죠", "흩어져야 함"),
    ("   화면 지목 전체(유지)", JIMOK, "줄면 안 됨"),
    ("   명사끊기 CTA(유지)", MYEONGSA, "줄면 안 됨"),
    ("★더라고요 계열(유지)", DEORA, "적을수록 좋음"),
]
for label, pat, note in rows:
    if pat is None:
        v3 = sum(1 for t in a3 if cta_order_bad(t))
        v4 = sum(1 for t in a4 if cta_order_bad(t))
    elif pat == "*":
        v3 = sum(1 for t in a3 if "*" in t)
        v4 = sum(1 for t in a4 if "*" in t)
    else:
        v3, v4 = cnt(a3, pat), cnt(a4, pat)
    print(f"  {label:26} 3차 {v3:3} → 4차 {v4:3}   ({note})")

# 대본당 '보이시죠' 2회 이상
multi = [p["job_id"][:8] for p in p4 if p["after4"].count("보이시죠") >= 2]
if multi:
    print(f"  ⚠️'보이시죠' 대본 내 2회+: {multi}")

# 전규칙 통과 (check3와 동일 기준 + 4차 결함)
bad = Counter()
ok = 0
detail = {"len": []}
for p in p4:
    a, b = p["after4"], p["before"].replace(" / ", " ")
    probs = []
    if len(DEORA.findall(a)) > 1:
        probs.append("더라고요")
    if a.count("것 같아요") > 1 or a.count("거 있죠") > 1:
        probs.append("감시표현")
    if ", 글쎄" in a:
        probs.append("글쎄")
    if [c for c in CLICHE if c in a]:
        probs.append("상투어")
    r = len(a) / len(b) if b else 0
    if not (0.80 <= r <= 1.30):
        probs.append("길이"); detail["len"].append((p["job_id"][:8], round(r, 2)))
    if cta_order_bad(a):
        probs.append("CTA순서")
    if "*" in a:
        probs.append("별표")
    if a.count("보이시죠") >= 2:
        probs.append("보이시죠중복")
    for x in probs:
        bad[x] += 1
    if not probs:
        ok += 1

print(f"\n[전규칙 통과] 4차 {ok}/{len(p4)}  (1차 26 / 2차 24 / 3차 32 — 단 4차는 검사항목 3개 추가)")
print(f"  위반내역: {dict(bad)}")
if detail["len"]:
    print(f"  길이이탈: {detail['len'][:10]}")

print("\n[4차 종결 4글자 상위 12]")
surf = Counter()
for a in a4:
    for s in re.split(r"(?<=[.!?…])\s+", a):
        s = s.strip().rstrip(".!?…")
        if len(s) >= 3:
            surf[s[-4:]] += 1
for s, c in surf.most_common(12):
    print(f"  ...{s}: {c}")
print(f"[고유 종결형] 4차 {len(surf)}종")
