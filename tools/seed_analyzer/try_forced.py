# -*- coding: utf-8 -*-
"""고조를 **구조로 강제**하는 실험 (2026-09-22 사장님
   "억지로 썼나가 아니라 그렇게 쓸수밖에 없게 프롬포트를 만드는 연구를해봐").

★왜 검사로는 안 되나: 지금 프롬프트는 "고조가 2칸이어도 된다"(허용) ·
  "억지로 늘리지 마라"(금지)로 말한다. 모델에게 칸 수 선택권이 남아 있으면 채운다 —
  실측 2026-09-22: 같은 프롬프트로 2편을 뽑았는데 한 편은 2칸으로 깊게 파고(좋음)
  한 편은 4칸을 만들다 **칸마다 1줄로 쪼그라들었다**(나쁨). 금지문은 안 지켜진다.

★그래서 세 가지를 비교한다:
  A 칸깔기  코드가 pain 센 것을 골라 [고조1][고조2] 자리를 미리 깔아 준다 → 칸 수를 모델이 못 정한다
  B 형식강제 고조를 {순간, 벌어지는일, 없애버림} 3필드로 받는다 → 1줄로 뭉치는 게 구조적으로 불가능
  C 생각먼저 쓰기 전에 "언제·뭐가·몇 번"을 답하게 하고 그 답으로 쓴다

쓰기(서버, env 필요):
  python3 tools/seed_analyzer/try_forced.py --mode B --n 2
  python3 tools/seed_analyzer/try_forced.py --mode ALL
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")

from try_writer import DEMO, flat_lines, money_lines  # noqa: E402
from cases import CASES  # noqa: E402
from signal_sets import signals_for, pick_set, make_key  # noqa: E402

# ── B: 고조를 3필드로 받는다 — 한 줄로 뭉칠 수가 없다 ──────────────────────────
SCHEMA_B = {
    "type": "object",
    "properties": {
        "hook": {"type": "string"},
        "bait": {"type": "string"},
        "reveal": {"type": "string"},      # "이건 바로 {제품명}" — 짧게 끊는다(실측)
        "contrast": {"type": "string"},    # 기존 것의 한계 — 고조1 앞에 대비로 건다(없으면 빈칸)
        "escalations": {"type": "array", "items": {"type": "object", "properties": {
            # ★signal은 **코드가 세트에서 박는다** — 모델에게 고르게 하면 가장 흔한 하나로 쏠린다
            #   (실측 2026-09-22: 후보를 줬더니 2편 모두 "이게 진짜 말도 안 되는 게"만 썼다).
            "moment": {"type": "string"},      # 그 불편이 벌어지는 순간
            "what_happens": {"type": "string"},  # 그때 벌어지는 일 + 반복되는 괴로움
            "erased": {"type": "string"},      # 그걸 어떻게 통째로 없앴나
            "from_pain": {"type": "string"},   # 근거로 삼은 재료의 '이게 없을 때'
        }, "required": ["moment", "what_happens", "erased", "from_pain"]}},
        "twist": {"type": "string"},
        "closing": {"type": "string"},
    },
    "required": ["hook", "bait", "reveal", "contrast", "escalations", "twist", "closing"],
}

BRIEF_B = """너는 한국 쇼핑 숏폼 나레이션 작가다.

■ 설명문을 쓰지 마라
"A는 B 기능이 있어 편리합니다" 같은 문장은 한 줄도 쓰지 마라.
제품 설명서가 아니라 그 장면을 보고 있는 사람의 말이다.
  X 원래 두피 영양제는 손에 묻어서 바르기 불편하지만
  O 겨우 짜서 바르려는데 손가락 사이로 다 흘러내리고 머리만 떡져서

■ reveal — **짧게 끊어라**
"이건 바로 {제품명}." 로 끝낸다. 뒤에 설명을 이어 붙이지 마라.
제품 이름 자체에 특징이 들어 있으면 그대로 쓴다("심이 필요 없는 호치키스", "말랑한 실리콘 국자").
실측(썰채널 30편): 공개 줄은 거의 전부 제품명만 말하고 바로 다음 칸으로 넘어간다.
꾸밈은 여기가 아니라 **contrast와 고조**에서 한다.

■ contrast — 기존 것의 한계를 걸어 대비를 만든다 (실측에서 가장 자주 쓰는 기법)
"온도를 유지만 시켜 주던 기존 컵홀더와는 달리" · "기존 주방 환풍기는 아무리 세게 틀어도 한계가 있는데"
· "007 가방 크기 급의 거추장스러운 버너와 달리"
재료에 기존 방식의 불편이 있으면 그걸로 쓰고, 댈 게 없으면 **빈칸으로 둬라**(지어내지 마라).

■ escalations — 재료의 "이게 없을 때"가 **진짜 괴로운 것만** 넣어라
칸 수를 채우려 하지 마라. 1개여도 되고 2개여도 된다.
from_pain에는 근거로 삼은 재료의 '이게 없을 때' 문장을 **그대로** 적어라.
근거로 댈 게 없으면 그 칸을 만들지 마라.

칸을 여는 신호어("심지어", "이게 말도 안 되는게" 같은 말)는 **우리가 붙인다. 네가 쓰지 마라.**
moment는 신호어 다음에 바로 이어질 말로 시작해라.

칸 하나는 이렇게 채운다 (없는 걸 지어내지 말고 **있는 불편을 깊게 파라**):
  moment        그 불편이 벌어지는 **순간**을 현재형으로   "겨우 재워놓고 바닥에 내려놓는 순간"
  what_happens  그때 벌어지는 일 + 반복되는 괴로움        "등이 닿자마자 눈을 번쩍 떠서 다시 재우던 그 지옥을"
  erased        그걸 통째로 없앤 방식, 강한 동사로 끊기    "자리를 아예 하나로 합쳐서 없애 버렸다는 거"
                ★what_happens가 "~을/를"로 끝나면 erased는 그 목적어를 받는 서술어로 이어져야 한다.
                  어색하면 "없애기" 표현을 억지로 붙이지 말고 자연스러운 말로 끊어라.
                  X "완벽한 방수층을 만들어 사라지게 버리는데"  (표현을 겹쳐 붙여 꼬였다)
                  O "발라서 굳히기만 하면 그대로 방수층이 돼 버린다는 거"

■ twist는 앞 고조와 **다른 축**이어야 한다
앞이 기능이었으면 위생·보관·휴대 같은 다른 걱정거리를 꺼낸다. 기능을 하나 더 나열하면 반전이 아니다.

■ closing은 권유가 아니다
"~해 보세요", "~하세요" 금지. 남의 말로 닫아라 — "…다 줄여 버렸다고", "…난리라는데".

■ 표현 재료 (골라 쓰는 것이다. 이 재료에 안 맞으면 쓰지 마라)
  의태어  싹·착·탁·쓱·확·쏙·슥·쭉·뚝딱·똑·푹·사르르·살살·번쩍
  고통    지옥·진절머리·빡쳤던·노이로제·스트레스·귀찮·답답·짜증
  없애기  없애 버렸다는 거 · 사라져 버리는데 · 줄여 버렸다고 · 날려 버려서
  증언    난리라는데 · 품절 대란 · 입소문이 터지며 · 쓰는 사람이 많다는데
  폭넓히기 거실이든 안방이든 차 안이든 (장소·상황 셋씩)

■ 표현은 자유롭게 — 후킹이 전부다 (2026-09-22 사장님)
불편·상황·인물·수치·효능·가격은 **화면에 없어도 쓸 수 있다.** 그 제품을 쓰는 사람이
겪을 법한 일이면 된다. 사용자가 나중에 고치면 되니 **세게, 구체적으로** 써라.
★다만 장면을 아주 못 만들 정도로 화면과 동떨어진 말은 피해라 — 우리는 이 재료로 화면을 붙인다.

■ 지키는 것
- 문장을 마침표로 딱 끊지 말고 연결어미로 이어라.
- 씨앗의 말투는 가져오되 문장은 베끼지 말고 새로 써라."""


def prompt_b(d):
    rows = ["[제품] %s" % d["product"], "",
            "[씨앗 — 이 제품으로 터진 영상의 말]", d["seed"].strip(), "",
            "[재료]"]
    for f in d["feats"]:
        rows.append("- %s — %s" % (f["name"], f["claim"]))
        if f.get("pain"):
            rows.append("    이게 없을 때: %s" % f["pain"])
    return "%s\n\n%s" % (BRIEF_B, "\n".join(rows))


def lines_from_b(o, key="demo", nth=0):
    """B의 구조 출력을 대본 줄로 편다. ★신호어는 **여기서 코드가 박는다**(세트 순번)."""
    escs = o.get("escalations") or []
    set_name, sigs = signals_for(key, len(escs), nth)
    out = [("훅", o.get("hook")), ("미끼", o.get("bait")), ("공개", o.get("reveal"))]
    if (o.get("contrast") or "").strip():
        out.append(("대비", o["contrast"]))
    for i, e in enumerate(escs, 1):
        if sigs[i - 1]:
            out.append(("고조%d" % i, sigs[i - 1]))
        for k in ("moment", "what_happens", "erased"):
            if (e.get(k) or "").strip():
                out.append(("고조%d" % i, e[k]))
    out += [("반전", o.get("twist")), ("마무리", o.get("closing"))]
    return [{"beat": b, "text": t.strip()} for b, t in out if (t or "").strip()]


_REVEAL_OK = re.compile(r"이[건게] 바로|그게 바로")


def audit(lines, o, feats):
    rv = (o.get("reveal") or "").strip()
    pains = [(f.get("pain") or "").strip() for f in feats if (f.get("pain") or "").strip()]
    escs = o.get("escalations") or []
    # 근거 검사 — from_pain이 실제 재료의 pain과 닿아 있나(앞 8자로 대조)
    ungrounded = []
    for e in escs:
        fp = re.sub(r"\s+", "", e.get("from_pain") or "")
        if not fp or not any(re.sub(r"\s+", "", p)[:8] in fp or fp[:8] in re.sub(r"\s+", "", p)
                             for p in pains):
            ungrounded.append(e.get("from_pain") or "(빈칸)")
    thin = [i + 1 for i, e in enumerate(escs)
            if sum(1 for k in ("moment", "what_happens", "erased") if (e.get(k) or "").strip()) < 3]
    return {"esc": len(escs), "pain": len(pains), "ungrounded": ungrounded, "thin": thin,
            "reveal_len": len(rv), "reveal_form": bool(_REVEAL_OK.search(rv)),
            "contrast": bool((o.get("contrast") or "").strip()),
            "flat": flat_lines(lines), "money": money_lines(lines),
            "closing_cta": bool(re.search(r"(해|하)\s*보세요|하세요|드세요", o.get("closing") or ""))}


def run_b(n, keys=None, case=None):
    from shopping_shorts import script_generate as _sg
    d = CASES.get(case) or DEMO
    p = prompt_b(d)
    print("[B 형식강제 + 신호세트] 프롬프트 %d자\n" % len(p))
    # ★회원마다 다른 신호세트가 가는지 같이 본다(같은 씨앗을 쓴 회원이 5명까지 있었다)
    # 한 고객이 한 작업에서 n안을 뽑는 상황 — nth가 순번이라 세트가 반드시 갈린다
    key = make_key(57, case or "demo")
    for i in range(n):
        o = _sg._call_json(p, SCHEMA_B) or {}
        lines = lines_from_b(o, key, i)
        a = audit(lines, o, d["feats"])
        print("=== %d편 · %d줄 · 고조 %d칸(재료 불편 %d) ===" % (i + 1, len(lines), a["esc"], a["pain"]))
        print("    설명문 %d · 얇은칸 %s · 근거없음 %d · 마무리CTA %s · 돈 %d · 신호세트 %s"
              % (len(a["flat"]), a["thin"] or "없음", len(a["ungrounded"]),
                 "예" if a["closing_cta"] else "아니오", len(a["money"]),
                 pick_set(key, i)[0]))
        print("    공개 %d자·꼴 %s · 대비 %s"
              % (a["reveal_len"], "O" if a["reveal_form"] else "X",
                 "O" if a["contrast"] else "없음"))
        for l in lines:
            print("  [%s] %s" % (l["beat"], l["text"]))
        if a["ungrounded"]:
            print("  * 근거 못 댄 고조:", a["ungrounded"])
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="B")
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--case", default="")
    a = ap.parse_args()
    if a.case == "all":
        for name in CASES:
            print("\n########## %s ##########" % name)
            run_b(a.n, case=name)
    else:
        run_b(a.n, case=a.case or None)


if __name__ == "__main__":
    main()
