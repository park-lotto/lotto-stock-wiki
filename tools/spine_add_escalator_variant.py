# -*- coding: utf-8 -*-
"""오용형 스파인 `cases`에 **2슬롯짜리 고조어 변형**을 넣는다 — 멱등 마이그레이션.

## 왜 필요한가

`spine_fill`이 반전(twist) 몫을 먼저 떼어내도록 고쳐지면서(2026-08-20), cases가 쓰는
사용처가 하나씩 줄었다. 그대로 두면 **사용처 3개** 구간에서 고조어('심지어')가 사라진다.

    사용처 3개 → cases "…고수들은 B까지 하더라고요"   ← '심지어' 없음
                 twist "근데 미친 사용법은 따로 있었는데 C"
    script_gate 「고조 심화(1회)」 검사는 대본 전체에서 고조어 **정확히 1회**를 요구한다
    → 0회라 FAIL.

실측(raw/analysis/썰쇼핑_히트작200_2026-08-20, 오용형 정밀분해 20편)의 사용처 개수는
2개 5편 · 3개 6편 · 4개 6편 · 5개 3편이라 **3개 구간이 30%**다. 그냥 두면 안 된다.

그래서 2슬롯만으로도 고조어가 들어가는 변형을 **3슬롯 변형 바로 뒤에** 끼운다.
`pick_template`은 "슬롯이 전부 채워지는 첫 번째"를 고르므로 순서가 곧 우선순위다:

    사용처 4개 이상 → 3슬롯 변형(심지어 1회)      ← 종전 그대로
    사용처 3개      → 2슬롯 고조 변형(심지어 1회)  ← 이번에 살리는 구간
    사용처 2개      → 1슬롯 변형(고조어 없음)      ← 종전 그대로(재료가 얇은 건 별개 문제)

## ⚠️ 왜 `tools/seed_style_youtube.py`를 안 쓰나

그 시드는 **라이브보다 낡았다**(2026-08-20 실측). 라이브 spine 56의 twist는 `{용도끝}`인데
시드는 `{용도}`이고, `cases`·`bait`·`title`은 시드에 아예 없다. 시드를 다시 돌리면
`set_spine_style(templates=...)`가 통째로 덮어써서 **라이브 템플릿이 퇴화한다.**
그래서 여기서는 cases 목록만 읽어 없으면 끼우고, 나머지는 손대지 않는다.

실행: python3 tools/spine_add_escalator_variant.py   (서버에서 돌린다 — DB가 거기 있다)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts.config import DB_PATH          # noqa: E402
from shopping_shorts.store import Store             # noqa: E402

SPINE_NAME = "유튜브 오용형"

# 3슬롯 변형(있으면 그 **바로 뒤**에 끼운다). 없으면 맨 앞에 둔다.
THREE = "심지어 {용도3}"
VARIANT = "초보들은 기껏해야 {용도} 정도가 전부였는데 고수들은 심지어 {용도2}까지 하더라고요"


def patch(templates):
    """(새 templates, 바뀌었나). 원본을 건드리지 않는다."""
    t = dict(templates or {})
    cases = list(t.get("cases") or [])
    if any(VARIANT == c for c in cases):
        return t, False
    at = len(cases)
    for i, c in enumerate(cases):
        if THREE in c:
            at = i + 1
            break
    cases.insert(at, VARIANT)
    t["cases"] = cases
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
        print("이미 들어 있다(멱등) — id=%s" % sp["id"])
        return 0
    st.set_spine_style(sp["id"], templates=new)      # templates만 넘긴다(나머지는 None=유지)
    after = [s for s in st.list_spines() if s["id"] == sp["id"]][0]
    print("갱신: id=%s  cases %d개 → %d개"
          % (sp["id"], len(sp.get("templates", {}).get("cases") or []),
             len(after.get("templates", {}).get("cases") or [])))
    for i, c in enumerate(after["templates"]["cases"], 1):
        print("  %d. %s" % (i, c))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
