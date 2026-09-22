# -*- coding: utf-8 -*-
"""같은 재료 × 스타일별 스토리라인 (2026-09-22 사장님).

★승인 스타일 24개를 실측해 보니 칸 구성이 몇 갈래로 뭉친다(2026-09-22):
  · 55·74·75·76 = title·bait·fame·reveal·limit·solve·more…  **9칸 동일**(훅 각도만 다름)
  · 56·70·71·72·73 = title·bait·origin·notice·cases·escalation·twist  **7칸 동일**(오용 흐름)
  · 52·58·59·61·62 = 인스타(존댓말·CTA 있음) — 스토리라인이 각자 다르다
  · 1·2·3·4 = beat_roles가 **0칸인 빈 껍데기**(아무 일도 안 한다 — 정리 대상)

★★빈칸 채우기를 하지 않는다 (2026-09-22 사장님 "지금은 대본스타일이 다 빈칸채우기로 되어있는거 아닌가?")
  라이브 스파인은 `{적용대상}, 이게 그렇게 된다고요?`처럼 **완성 문장에 구멍**을 뚫어 두고
  모델에게 메우게 한다 → 조사·어미가 안 맞아 "가성비밖에 안 한다는 점이에요" 같은 비문이 난다.
  여기서는 문형을 **"이런 각도로 첫 줄을 써라"**는 설명으로만 주고, 문장은 모델이 처음부터 쓴다.

★오용형(70)은 **이야기 거푸집**이라 재료에 딴 용도가 없으면 모델이 지어낸다
  (실사고: 두피빗에 "초보는 토닉만 바르고 고수는 마사지 도구로"를 창작).
  그래서 alt_use(딴 용도)가 재료에 있는지 **코드가 먼저 보고**, 없으면 그 스타일을 뺀다.

쓰기(서버, env 필요):
  python3 tools/seed_analyzer/try_styles.py --case 뮤지엄젤
  python3 tools/seed_analyzer/try_styles.py --case 뮤지엄젤 --only 인스타
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
sys.path.insert(0, HERE)

from cases import CASES  # noqa: E402
from signal_sets import signals_for, make_key  # noqa: E402
from try_forced import (SCHEMA_B, BRIEF_B, lines_from_b, audit)  # noqa: E402


INSTA_VOICE = """
■ 인스타 결 (메종·홈테리어픽 95편 실측 2026-09-22)
- 존댓말 1인칭. **내가 보고 겪은 일**로 말한다. 정체를 감추지 마라(유튜브 썰과 반대).
- 문장 끝은 **~더라고요**(95~98%가 쓴다) · ~거든요 · ~어요.
  ★유튜브 썰의 `~다는데`·`~버렸다는 거`를 쓰면 인스타가 아니다.
- 순서는 **사건 순서**다: 계기 → 발견 → 정체 → 결과 → 사람들 반응.
- 감탄을 자주 쓴다(66~69%): 와 · 진짜 · 소리질렀어요 · 미쳤.
- 지인(와이프·엄마·친구·사장님)이 나오면 이야기가 산다. 재료나 씨앗에 있을 때만 쓰고 지어내지 마라.
- 가격은 거의 쓰지 않는다(2~7%). 재료에 값이 있을 때만.
"""

# 계열별 스토리라인 — 실측한 칸 구성을 **설명으로** 옮긴 것(빈칸 틀이 아니다)
STYLES = {
    "오용형": {
        "spine": 70, "name": "유튜브 「OO도 예상 못한 미친 활용법」",
        "tone": "반말", "cta": False, "needs_alt_use": True,
        "hook_angle": "권위자(개발자·제조사·본사·직원)도 예상 못했다는 각도로 연다",
        "flow": "훅 → 미끼(요새 이거 하나로 난리) → 본래 용도 → 사람들이 다르게 쓰기 시작 "
                "→ 실제 사례 → 고조 → 반전",
        "extra": ("■ 이 스타일은 **딴 용도 이야기**다\n"
                  "원래 무엇으로 만든 물건인지 먼저 밝히고, 사람들이 전혀 다르게 쓰기 시작했다는 흐름이다.\n"
                  "★재료에 원래 용도와 다른 쓰임이 없으면 억지로 지어내지 마라 — 대본이 거짓이 된다."),
    },
    "발명품형": {
        "spine": 75, "name": "유튜브 「OO을 구원한 천재의 발명품」",
        "tone": "반말", "cta": False, "needs_alt_use": False,
        "hook_angle": "누구를(무엇을) 구원한 천재의 발명품이라는 각도로 연다",
        "flow": "훅 → 미끼(최근 SNS에서 난리) → 만든 사람 성과 → 정체공개 → 대비 → 고조 → 반전 → 마무리",
        "extra": ("■ 이 스타일은 **발명 이야기**다\n"
                  "누가 왜 만들었는지, 그래서 어떤 성과를 냈는지로 판을 깐 뒤 정체를 밝힌다.\n"
                  "★나라·개발자는 재료나 씨앗에 있을 때만 쓴다. 없으면 '해외'처럼 두루뭉술하게 두거나 빼라."),
    },
    "인스타·정체의문": {
        "spine": 61, "name": "정체의문형(인스타)",
        "tone": "존댓말", "cta": True, "needs_alt_use": False,
        "hook_angle": "\"이게 그렇게 된다고요?\"처럼 믿기지 않는다는 의문으로 연다",
        "flow": "훅(의문) → 내 사정(불편해서 알아보던 중) → 알고 보니 정체 → 특징 → 결과 → 고조 → CTA",
        "extra": ("■ 인스타 — **내가 겪은 이야기**다\n"
                  "- 존댓말 1인칭. \"저 이거 보고 진짜 놀랐어요\"처럼 내 경험으로 말한다.\n"
                  "- 마지막 줄은 **CTA**: \"궁금하시면 댓글에 'OO' 남겨주세요\" 꼴로 닫는다."),
    },
    "인스타·가족갈등": {
        "spine": 52, "name": "가족갈등 반전형(인스타)",
        "tone": "존댓말", "cta": True, "needs_alt_use": False,
        "hook_angle": "아는 사람(친구·언니·지인) 집에 갔다가 충격받았다는 각도로 연다",
        "flow": "훅(충격) → 그 사람 것이 달랐다 → 눈치챔 → 물어봄 → 정체공개 → 방법 "
                "→ 결과 → 고조 → 왜 이제 알았나 → CTA",
        "extra": ("■ 인스타 — **남에게서 발견한 이야기**다\n"
                  "- 존댓말 1인칭. 남의 집·남의 물건을 보고 놀란 흐름이다.\n"
                  "- 인물(친구·언니·엄마·지인)이 반드시 나온다. 재료에 없으면 씨앗의 인물을 쓴다.\n"
                  "- 마지막 줄은 CTA."),
    },
    "인스타·금지경고": {
        "spine": 58, "name": "금지경고형(인스타)",
        "tone": "존댓말", "cta": True, "needs_alt_use": False,
        "hook_angle": "\"절대 이렇게 하지 마세요\"라는 경고로 연다",
        "flow": "훅(하지 마라) → 나도 그랬다 → 이유 → 올바른 방법 → 결과 → 고조 → CTA",
        "extra": ("■ 인스타 — **경고로 여는 이야기**다\n"
                  "- 존댓말. 첫 줄은 하지 말라는 경고로 시선을 잡는다.\n"
                  "- '나도 그렇게 하다 손해 봤다'를 깔고 올바른 방법으로 넘어간다.\n"
                  "- 권위(전문가·사장님·업체)는 재료나 씨앗에 있을 때만 쓴다. 없으면 빼라.\n"
                  "- 마지막 줄은 CTA."),
    },
}


def has_alt_use(d):
    """재료에 '원래 용도와 다른 쓰임'이 있나 — 오용형을 걸러내는 근거."""
    blob = " ".join([d.get("seed", "")] + [f.get("claim", "") + f.get("pain", "") for f in d["feats"]])
    return bool(re.search(r"원래[는 ]|본래|용도로 만든|다르게 쓰|엉뚱|의류매장|박물관", blob))


def build(d, st):
    rows = ["[제품] %s" % d["product"], "",
            "[씨앗 — 이 제품으로 터진 영상의 말]", d["seed"].strip(), "",
            "[재료]"]
    for f in d["feats"]:
        rows.append("- %s — %s" % (f["name"], f["claim"]))
        if f.get("pain"):
            rows.append("    이게 없을 때: %s" % f["pain"])
    # ★문형을 주지 않는다 — 각도만 준다. 문장은 모델이 처음부터 쓴다(빈칸 채우기 금지)
    style_block = ("\n\n■ 이번 대본의 스타일: %s\n말투: %s\n스토리라인: %s\n첫 줄(훅) 각도: %s\n%s"
                   % (st["name"], st["tone"], st["flow"], st["hook_angle"], st["extra"]))
    if st["tone"] == "존댓말":
        style_block += "\n" + INSTA_VOICE
    if st["cta"]:
        style_block += ("\n★이 스타일은 마무리가 CTA다 — closing에 "
                        "\"궁금하시면 댓글에 'OO' 남겨주세요\" 꼴로 써라(유튜브 썰의 '난리라는데'로 닫지 마라).")
    return BRIEF_B + style_block + "\n\n" + "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="뮤지엄젤")
    ap.add_argument("--only", default="", help="이름에 이 말이 든 스타일만")
    a = ap.parse_args()
    from shopping_shorts import script_generate as _sg
    d = CASES[a.case]
    alt = has_alt_use(d)
    print("재료: %s · 딴 용도 이야기 %s\n" % (a.case, "있음" if alt else "없음"))

    for i, (key, st) in enumerate(STYLES.items()):
        if a.only and a.only not in key:
            continue
        if st["needs_alt_use"] and not alt:
            print("########## %s — 건너뜀(재료에 딴 용도가 없어 이 흐름은 성립 안 함) ##########\n" % key)
            continue
        o = _sg._call_json(build(d, st), SCHEMA_B) or {}
        lines = lines_from_b(o, make_key(57, a.case), i)
        au = audit(lines, o, d["feats"])
        print("########## %s (스파인 %d) ##########" % (key, st["spine"]))
        print("  설명문 %d · 얇은칸 %s · 근거없음 %d · 고조 %d칸"
              % (len(au["flat"]), au["thin"] or "없음", len(au["ungrounded"]), au["esc"]))
        for l in lines:
            print("  [%s] %s" % (l["beat"], l["text"]))
        print()


if __name__ == "__main__":
    main()
