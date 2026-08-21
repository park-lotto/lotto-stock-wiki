# -*- coding: utf-8 -*-
"""은폐형(spine 55) twist 변형의 **비문**을 고친다 — 멱등 마이그레이션 (2026-08-21).

## 무엇이 잘못됐나

    "근데 진짜 충격적인 포인트는 {효능2} 심지어 {효능3}까지 된다는 거"

`{효능3}`은 대개 **문장**이다("성인 체중을 충분히 지탱하는 압도적 부력을 제공한다").
그 뒤에 "까지 된다는 거"가 붙으면 이렇게 나간다:

    "…압도적 부력을 제공한다까지 된다는 거"

★게이트는 이걸 **못 잡는다** — 문장틀·글자수·고조어를 전부 통과한다(실측 15/15).
  발명품형 escalate에서 똑같은 비문을 이미 고쳤는데(2026-08-20) 은폐형에 남아 있었다.

## 어떻게 고치나

`{효능3}`을 붙이는 어미를 **문장 뒤에 자연스러운 형태**로 바꾼다:

    바꾸기 전: "근데 진짜 충격적인 포인트는 {효능2} 심지어 {효능3}까지 된다는 거"
    바꾼 뒤  : "근데 진짜 충격적인 포인트는 {효능2} 심지어 {효능3}"

고조어('심지어')는 그대로 남아 게이트의 「고조 심화(1회)」를 계속 통과한다.

실행: python3 tools/spine55_fix_twist_josa.py   (서버 — DB가 거기 있다)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts.config import DB_PATH          # noqa: E402
from shopping_shorts.store import Store             # noqa: E402

SPINE_NAME = "유튜브 은폐형"
OLD = "근데 진짜 충격적인 포인트는 {효능2} 심지어 {효능3}까지 된다는 거"
NEW = "근데 진짜 충격적인 포인트는 {효능2} 심지어 {효능3}"


def patch(templates):
    t = dict(templates or {})
    tw = list(t.get("twist") or [])
    if OLD not in tw:
        return t, False
    t["twist"] = [NEW if x == OLD else x for x in tw]
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
        print("이미 고쳐져 있다(멱등) — id=%s" % sp["id"])
        return 0
    st.set_spine_style(sp["id"], templates=new)      # templates만 넘긴다(나머지 유지)
    after = [s for s in st.list_spines() if s["id"] == sp["id"]][0]
    print("갱신: id=%s" % sp["id"])
    for i, x in enumerate(after["templates"]["twist"], 1):
        print("  %d. %s" % (i, x))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
