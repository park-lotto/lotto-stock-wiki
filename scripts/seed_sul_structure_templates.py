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
MISUSE = {
    "title": ["제조사도 예상 못 한 {제품군} 활용법",
              "개발자도 몰랐던 {제품군} 사용법",
              "만든 사람도 예상 못 한 뜻밖의 활용법"],
    "cases": ["{용도들}",
              "{용도}로 쓰더라고요"],
}
# 은폐형(spine 55) — 정체를 reveal까지 숨긴다. title에 제품명이 들어가면 안 된다.
CONCEAL = {
    "title": ["{나라} 천재가 만들어 떼돈 번 {제품군}의 정체",
              "{나라} 천재를 돈방석에 앉힌 제품의 정체",
              "개발자도 예상 못 한 이 제품의 정체"],
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
    print("#%s %s | 채울 칸: %s (이미 있는 칸은 안 건드린다)"
          % (sp["id"], sp["name"], list(changed) or "없음"))
    if changed and apply_:
        cur.update(changed)
        st.set_spine_style(sp["id"], templates=cur)
print("적용됨" if apply_ else "미적용(--apply를 붙여라)")
