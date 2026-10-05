# -*- coding: utf-8 -*-
"""말맛 대조 — 원본 12편(scripts_*.json) vs 우리가 뽑은 대본(시험 결과 json).
사용: PYTHONUTF8=1 py taste_compare.py <scripts_원본.json> <시험결과.json> [...]
잰 것(본문만): 줄당 글자 · 설명서 낱말(방식·구조·용도·가능…) 100자당 수 · 입말·비유·의태어 100자당 수 ·
             편마다 똑같이 들어가는 고정 문장이 차지하는 글자 비율 · 제목이 '사건 동사'를 갖는 편 수.
★낱말 목록은 손으로 고른 것이다 — 절대값보다 원본과 우리 것의 **차이**를 본다."""
import json, re, sys, statistics as st

MANUAL = r"방식|구조|용도|가능|제공|외관|부착|활용|손상|변형|사용할 수|제거|수정|보강|고정력|완성|조절|인증|소재|재질|구성|분해|안심"
TASTE = r"노맛|빵돌이|맛잘알|인간사료|쟁여|꽂힌|시전|개시원|따땃|찝찝|씹어먹|털어|낙하산|고딩|호기롭게|마치|처럼|쓱|싹|착|콕|쏙|뚝딱|와르르|박박|ㄷㄷ|ㅋㅋ|미친|환장|진심"
FIXED = [r"사람들이 이걸 (사는|구매하는) 이유는 단순히", r"때문이 아니라는데", r"그러나 정작 .{1,25} 꽂힌 포인트는 따로 있다는데", r"그건 바로",
         r"본 사람들이 놀란 부분이 있는데", r"할 수가 있냐는 거", r"사실 보통", r"단점이 있었음", r"하지만 이건", r"이유가 없어져버렸다고", r"끝에 이걸 발견해버렸는데"]
EVENT = r"버린|씹어먹|털어|빼앗|해킹|유출|만든|알려준|탄생|성공시킨|환장|구원|망하게|박살"


def chars(t): return len(re.sub(r"\s", "", t))


def stats(name, items):
    """items = [(title, [줄…])]"""
    per_line = [chars(l) for _, ls in items for l in ls]
    body = [" ".join(ls) for _, ls in items]
    tot = sum(chars(b) for b in body)
    man = sum(len(re.findall(MANUAL, b)) for b in body); tas = sum(len(re.findall(TASTE, b)) for b in body)
    fixed = sum(sum(chars(m.group(0)) for p in FIXED for m in re.finditer(p, b)) for b in body)
    ev = sum(1 for t, _ in items if re.search(EVENT, t))
    print("%-10s 편 %2d · 줄당 글자 중앙 %4.1f (최장 %d) · 설명서 낱말 %.1f/100자 · 입말·비유 %.1f/100자 · 고정 문장 %.0f%% · 제목에 사건 동사 %d/%d"
          % (name, len(items), st.median(per_line), max(per_line), man / tot * 100, tas / tot * 100, fixed / tot * 100, ev, len(items)))


gold = [(next(t for g, t in v["lines"] if g == "T"), [t.replace("/", " ") for g, t in v["lines"] if g not in ("T", "C")])
        for v in json.load(open(sys.argv[1], encoding="utf-8"))["videos"]]
stats("원본", gold)
for p in sys.argv[2:]:
    ours = [(s["script"]["title"], [L["text"] for L in s["script"]["lines"]]) for j in json.load(open(p, encoding="utf-8"))["jobs"] for s in j.get("scripts") or []]
    if ours:
        stats("우리", ours)
        for k in ("hidden", "mechanism", "substitute"):
            sub = [(s["script"]["title"], [L["text"] for L in s["script"]["lines"]]) for j in json.load(open(p, encoding="utf-8"))["jobs"] for s in j.get("scripts") or [] if s["kind"] == k]
            if sub: stats(" └" + k, sub)
