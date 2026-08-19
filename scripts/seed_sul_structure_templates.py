# -*- coding: utf-8 -*-
"""썰쇼핑 구조 템플릿의 **빈 칸을 채운다**(2026-08-19).

사장님 지시: "구조템플릿 만드는게 중요해. 같은 해외영상이나 여러영상을 가져와도
거기에 딱 들어갈 말들만 있음 되게"

실측(같은 날): spine 56은 5칸 중 `title`·`cases`에 템플릿이 **아예 없었다** →
조립하면 3칸만 나오고 두 칸은 모델이 지어낸다. 그 두 칸을 못 박는다.

문장은 **지어내지 않았다** — 후보 채널 8곳의 실제 제목 54편에서 반복된 형태를 썼다:
    "제조사도 예상 못 한 뜻밖의 활용법"        (썰쇼템 1.37만)
    "이케아 직원도 감탄한 신박한 사용법"        (이거였네)
    "미국 천재의 역발상으로 떼돈 번 제품 정체"   (이왜템)
    "{용도}로 쓰는가 하면 …"                  (살림킹왕짱 전사)

★변형을 여러 개 두는 이유: `pick_template`이 **슬롯이 전부 채워지는 첫 문장**을 고른다.
  뒤로 갈수록 슬롯이 적어지게 배열해, 재료가 부족한 영상에서도 칸이 빈 채 나가지 않는다.

실행: python3 scripts/seed_sul_structure_templates.py [--apply]
"""
import sys
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")

from shopping_shorts.app import DB_PATH
from shopping_shorts.store import Store

# 오용형(spine 56) — 정체는 밝히고 용도를 뒤집는다.
# 오용형(spine 56) — 정체는 밝히고 용도를 뒤집는다.
# ★2026-08-19 실측 갱신: 살림킹왕짱 실제 자막 6편을 받아 읽고 구조를 다시 맞췄다.
#   (그 전 템플릿은 실측을 안 보고 만든 것이라 조립본이 123자 = 실측 234~284자의 절반이었다)
#   실제 결:
#     title : "제조사도 극찬한 한국 주부의 사용법"
#     bait  : "요새 주부들 사이에서 논란이 되고 있는 아이템이 하나 있는데"   ← 칸이 아예 없었다
#     origin: "이게 원래는 캠핑 텐트에 거는 용도로 나온 휴대용 실링팬이었음"  ← 제품군을 말한다
#     notice: "그런데 주부들은 어디든 달 수 있다는 점에 주목하면서"
#     cases : "초보 주부들은 기껏해야 환기 정도 하는게 전부였음.
#              하지만 고수 주부들은 주방 벽에 설치해서 시원하게 요리한다고"  ← 초보 vs 고수 대비
#     twist : "근데 미친 활용법은 따로 있었는데 …"
MISUSE = {
    "title": ["제조사도 예상 못 한 {제품군} 활용법",
              "개발자도 몰랐던 {제품군} 사용법",
              "만든 사람도 예상 못 한 뜻밖의 활용법"],
    "bait": ["요새 이 {제품군} 하나로 난리가 났는데",
             "최근 미친 아이디어 하나로 SNS 뒤집어 놓은 아이템이 하나 있는데"],
}
# 은폐형(spine 55) — 정체를 reveal까지 숨긴다. title에 제품명이 들어가면 안 된다.
CONCEAL = {
    "title": ["{나라} 천재가 만들어 떼돈 번 {제품군}의 정체",
              "{나라} 천재를 돈방석에 앉힌 제품의 정체",
              "이 {제품군}의 정체를 알면 다들 놀란다",
              "개발자도 예상 못 한 이 제품의 정체"],
}
# ★2026-08-19 실측으로 추가: 해외 원본 영상만 담으면 `{나라}`가 자주 빈다
#   (영상이 제조국을 안 밝히면 sul_facts가 **지어내지 않고 비운다** — 옳은 동작이다).
#   그런데 authority 템플릿 3개가 **전부** {나라}를 요구해서 그 칸이 통째로 못 채워졌다
#   (실측: 영어 원본 1편으로 5/6칸, 빈 칸은 authority 하나뿐).
#   → 나라 없는 변형을 뒤에 둔다. `pick_template`이 슬롯 적은 쪽으로 자동으로 내려간다.
CONCEAL_FIX = {
    # ★고조 자리가 아예 없었다(실측 2026-08-19): 게이트는 '고조 심화 1회'를 요구하는데
    #   은폐형 twist 템플릿 어디에도 '심지어/더 대박인 건'이 없어 항상 FAIL이었다.
    #   장점이 3개 이상이면 고조형이 먼저 걸린다(길이도 그만큼 늘어난다).
    "twist": ["근데 진짜 충격적인 포인트는 {효능2} 심지어 {효능3}까지 된다는 거",
              "근데 진짜 충격적인 포인트는 {효능2}",
              "근데 진짜 충격적인 건 {효능2}"],
    "authority": ["이걸 개발한 {나라}의 천재가 돈방석에 앉았다는데",
                  "이걸 만든 {나라} 천재가 떼돈을 벌었다는데",
                  "이걸 만든 천재가 떼돈을 벌었다는데",
                  "이걸 개발한 사람이 돈방석에 앉았다는데"],
}

# ★조사 자리를 템플릿에 명시한다(2026-08-19 실측). 원래 templates의 origin은
#   "{본래용도} 개발된 제품이었음"이라 슬롯이 '마늘 다지기'면
#   "마늘 다지기 개발된 제품이었음"이 된다 — 실측 전사는 "의류 태그 부착용**으로**
#   개발된"이었다. 조사를 붙여두면 spine_fill이 받침에 맞춰 로/으로를 골라준다.
FIX = {
    "제품정체형": CONCEAL_FIX,
    "오용형": {
        # 제품군을 말한다 — 실측 "개발된 펀칭기였습니다" / "나온 휴대용 실링팬이었음".
        "origin": ["이게 원래는 {본래용도}로 개발된 {제품군}이었음",
                   "이게 원래는 {본래용도}로 개발된 제품이었음",
                   "원래대로라면 {본래용도}로 쓰는게 정석이었음"],
        # ★twist가 cases의 첫 사례를 그대로 되풀이하면 반전이 죽는다(실측:
        #   cases "인테리어 소품으로 쓰는가 하면…" / twist "…따로 있었는데 인테리어 소품").
        #   {용도끝}은 사례 목록의 **마지막**을 가리킨다.
        "twist": ["근데 미친 사용법은 따로 있었는데 {용도끝}",
                  "근데 미친 활용법은 따로 있는데 {용도끝}"],
        # ★cases는 이미 값이 있어서 '채울 칸'으로는 안 바뀐다 — 교정 대상에 둔다.
        #   명사 나열("A로 쓰는가 하면 B로도")은 실측과 다르다. 실제는 대비 구조다:
        #   "초보 주부들은 기껏해야 환기 정도가 전부였음 / 하지만 고수 주부들은 …"
        "cases": ["초보들은 기껏해야 {용도} 정도가 전부였는데 고수들은 {용도2}까지 하더라고요 심지어 {용도3}까지 한다는 거",
                  "초보들은 기껏해야 {용도} 정도가 전부였는데 고수들은 {용도2}까지 하더라고요",
                  "{용도들}",
                  "{용도}로 쓰더라고요"],
    },
}

BY_FIT = {"오용형": MISUSE, "제품정체형": CONCEAL}
apply_ = "--apply" in sys.argv

st = Store(DB_PATH)
for sp in st.list_spines(status="approved"):
    fits = set(sp.get("fit_categories") or [])
    add = {}
    for fit, tmpl in BY_FIT.items():
        if fit in fits:
            add.update(tmpl)
    if not add:
        continue
    cur = dict(sp.get("templates") or {})
    changed = {k: v for k, v in add.items() if not cur.get(k)}
    # 조사 자리 교정은 **이미 있는 칸도** 덮어쓴다(그게 고치는 목적이다).
    fixed = {}
    for fit, tmpl in FIX.items():
        if fit in fits:
            for k, v in tmpl.items():
                if cur.get(k) != v:
                    fixed[k] = v
    print("#%s %s | 채울 칸: %s | 조사 교정: %s"
          % (sp["id"], sp["name"], list(changed) or "없음", list(fixed) or "없음"))
    # ★구간 자체가 모자랐다 — 실측 대본엔 title 뒤에 미끼 한 문장이 있는데
    #   beat_roles에 그 칸이 없었다. 칸이 없으면 템플릿을 넣어도 조립에 안 실린다.
    roles = list(sp.get("beat_roles") or [])
    if "오용형" in fits and "bait" not in roles and "title" in roles:
        roles.insert(roles.index("title") + 1, "bait")
        print("     구간 추가: bait → %s" % roles)
    else:
        roles = None
    if (changed or fixed or roles) and apply_:
        cur.update(changed)
        cur.update(fixed)
        st.set_spine_style(sp["id"], templates=cur, beat_roles=roles)
print("적용됨" if apply_ else "미적용(--apply를 붙여라)")
