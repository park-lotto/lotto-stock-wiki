# -*- coding: utf-8 -*-
"""인스타 대본의 **이야기 장치**를 실측한다 (2026-09-22 사장님
   "인스타가 오히려 더 스토리성으로 퀄리티가 올라가야한다 표현력이 상황극모두").

★썰(유튜브)은 정보를 쌓아 올리는 글이고, 인스타는 **상황극**이다.
  그래서 재는 것이 다르다 — 신호어만이 아니라 대사·인물 반응·시간 표지·되돌아보기를 센다.
재료: 코퍼스 인스타 641편(+ 메종·홈테리어픽 95편은 따로도 뽑는다).
"""
import json
import re
import sys
import collections

SRC = "/tmp/hits_cls_all.json"
FOCUS = ("maison_homedino", "homterior_pick")

PATTERNS = {
    "고조 신호": r"(?:근데 )?(?:진짜 )?(?:충격적인|미친|대박인|놀라운)[^\s]{0,3} ?(?:포인트는?|건|점은?)"
                r"|심지어|게다가|거기다|더 좋은 건|제일 좋은 건|무엇보다",
    "따옴표 대사": r"[\"'“‘][^\"'”’]{4,30}[\"'”’]",
    "인물 반응": r"(엄마|어머니|아내|와이프|남편|친구|언니|시어머니|사장님|아이|딸|아들)"
               r"[가이은는도]?\s?[^.]{0,16}(했|하더|라고|물어|놀라|좋아|우셨|난리)",
    "시간 표지": r"얼마 전|어느 날|그날|지난주|며칠 전|요즘|처음엔|그때|이번에",
    "감탄 도입": r"(^|\s)와[ ,]|와 진짜|아니 이거|아니 왜",
    "되돌아보기": r"왜 이제|진작|이럴 줄|알았으면|후회",
    "직접 권유": r"(사|챙겨|해|써|담아)\s?(오세요|두세요|보세요|주세요|야 해요|셔야)",
    "비용 언급": r"\d+\s?만\s?원|수리|업체|견적",
    "전/후 대비": r"예전[엔에는]|원래[는 ]|기존[엔에는]|전에는|그동안",
}


def sentences(t):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", t or "") if x.strip()]


def main():
    rows = json.load(open(SRC, encoding="utf-8"))
    ig = [r for r in rows if r.get("platform") == "instagram"]
    focus = [r for r in rows if r.get("user") in FOCUS]
    sys.stdout.reconfigure(encoding="utf-8")

    for label, group in (("인스타 전체", ig), ("메종+홈테리어픽", focus)):
        n = len(group)
        print("=== %s %d편 ===" % (label, n))
        for k, p in PATTERNS.items():
            c = sum(1 for r in group if re.search(p, r.get("text") or ""))
            print("   %-12s %3d/%d (%d%%)" % (k, c, n, 100 * c // max(1, n)))
        print()

    # 고조 신호가 실제로 어떤 낱말인가 (인스타 전용)
    T = " ".join(r.get("text") or "" for r in ig)
    cc = collections.Counter(re.sub(r"\s+", " ", m.group(0)).strip()
                             for m in re.finditer(PATTERNS["고조 신호"], T))
    print("인스타 고조 신호 실측(3회 이상):")
    for k, v in cc.most_common(20):
        if v >= 3:
            print("   %-18s %3d" % (k, v))
    print()

    # 따옴표 대사 — 상황극의 핵심
    dl = collections.Counter()
    for r in ig:
        for m in re.finditer(PATTERNS["따옴표 대사"], r.get("text") or ""):
            dl[m.group(0)] += 1
    print("대사 예시(상황극):")
    for k, v in dl.most_common(14):
        print("   %-34s %d" % (k[:34], v))


if __name__ == "__main__":
    main()
