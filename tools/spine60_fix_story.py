# -*- coding: utf-8 -*-
"""발명품형(spine 60) story·authority를 **실측 결**로 바로잡는다 — 멱등 (2026-08-21).

## 무엇이 틀렸나 — 내 판단이 상위 2편에 끌려갔다

어제(08-20) 이 스파인을 만들 때 "탄생 배경이 이 갈래의 본체"라고 봤다. 근거는
590만(우산 홀더 "육아맘에 빡쳐서 탄생한")·260만(나이키 "뇌성마비 소년의 편지 한 통에
탄생한") 두 편이었다. 그런데 **23편 전체를 세어보니**:

    탄생 배경(계기) 있음 :  2편 ( 9%)
    권위(누가 주목·화제)  : 19편 (83%)

**91%는 계기가 없다.** 진짜 본체는 권위였다. 그래서 계기가 없는 소재에서는 story가
"누가 봐도 그냥 평범해 보이는 이 {제품군} 하나가…"라는 **밋밋한 폴백**으로 나갔다
(사장님이 담아주신 구명 팔찌 소재에서 실제로 그렇게 나왔다).

## 실측 원문이 답이다 (축영상 3RxLl0NeR2Q, 이븐쇼핑)

    "해경과 해군이 주목한 한국 천재의 발명품
     최근 이 손목에 끼는 밴드 제품이 전 세계 SNS에서 수천만 조회수로 바이럴이 폭발하며
     이걸 개발한 한국의 한 천재가 떼돈을 벌었다는데
     이건 바로 손목 구명조끼
     이게 말도 안 되는 게 …"

→ story 자리는 **화제성 + 정체 밝히기**, authority 자리는 **개발자가 떼돈**이다.
   계기 변형은 **맨 앞에 그대로 남긴다** — 있는 소재(9%)에서는 그게 제일 세다.

실행: python3 tools/spine60_fix_story.py   (서버 — DB가 거기 있다)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts.config import DB_PATH          # noqa: E402
from shopping_shorts.store import Store             # noqa: E402

SPINE_NAME = "유튜브 발명품형"

# 계기 변형은 유지하고, **폴백만** 실측 결로 바꾼다.
STORY = [
    "{계기}에서 탄생한 이 제품이 사람들 사이에서 조용히 퍼지기 시작했는데",
    "{계기} 때문에 만들어진 이 물건이 입소문을 타기 시작했는데",
    # ↓ 91%가 여기 걸린다. 실측 축영상의 문장을 그대로 쓴다(화제성 + 정체 밝히기).
    "최근 이 {제품}이 전 세계 SNS에서 수천만 조회수로 바이럴이 폭발하며",
    "요즘 이 {제품군} 하나가 품절대란이 날 정도로 난리가 났다는데",
]

# story가 화제성을 맡았으니 authority는 **개발자 쪽**으로 옮긴다(실측 원문 그대로).
#   그대로 두면 story와 authority가 둘 다 "바이럴 터졌다"라 같은 말을 두 번 하게 된다.
#   ⚠️첫 변형에 꼬리("그럴 만한 이유가 있음")를 붙였다 — 실측에도 있는 어구고
#     ("전 세계로 수출되며 초대박이 났다는데 그럴 만한 이유가 있었음"),
#     효능 문장이 짧은 소재에서 조립본이 말 밀도 하한(172자)에 못 미치는 걸 메운다
#     (실측: 나이키 소재 167자 → 178자).
AUTHORITY = [
    "이걸 개발한 {나라}의 천재가 떼돈을 벌었다는데 그럴 만한 이유가 있음",
    "이걸 만든 {나라} 천재가 돈방석에 앉았다는데",
    "이걸 만든 사람이 떼돈을 벌었다는데 그럴 만한 이유가 있음",
]


def patch(templates):
    t = dict(templates or {})
    if t.get("story") == STORY and t.get("authority") == AUTHORITY:
        return t, False
    t["story"] = list(STORY)
    t["authority"] = list(AUTHORITY)
    return t, True


def main():
    st = Store(DB_PATH)
    hit = [s for s in st.list_spines() if s["name"] == SPINE_NAME]
    if not hit:
        print("스파인 '%s'가 없다 — 아무것도 안 했다" % SPINE_NAME)
        return 1
    sp = hit[0]
    new, changed = patch(sp.get("templates"))
    if not changed:
        print("이미 반영돼 있다(멱등) — id=%s" % sp["id"])
        return 0
    st.set_spine_style(sp["id"], templates=new)
    after = [s for s in st.list_spines() if s["id"] == sp["id"]][0]
    print("갱신: id=%s" % sp["id"])
    for k in ("story", "authority"):
        print(" [%s]" % k)
        for x in after["templates"][k]:
            print("   -", x)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
