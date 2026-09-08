# -*- coding: utf-8 -*-
"""유튜브 스파인 3종 이름을 **사용자가 알아보는 말**로 바꾼다 (2026-09-09 사장님).

## 왜

화면에 뜨던 이름이 전부 분석 용어였다 — 은폐형 / 오용형 / 발명품형.
사장님: "제목들도 사용자들이 공감할수있게 스타일이름을 지어줘".
고른 결은 **훅 문장 그대로**다(실측 히트작 원문에서 뽑았다) — 이름만 봐도 결과물이 그려진다.
회사·브랜드 이름은 OO으로 비운다(사장님: "삼성 나라 이런건 oo으로").

| 옛 이름(id) | 새 이름 | 근거 |
|---|---|---|
| 은폐형(55) | 유튜브 「이건 바로 OO」 | reveal 칸 문장틀 그대로 |
| 오용형(56) | 유튜브 「원래 이렇게 쓰는 거 아닌데」 | origin 칸("이게 원래는 ~였음")을 말로 |
| 발명품형(60) | 유튜브 「OO 개발자도 무릎 탁」 | 실측 훅(원문은 회사명 — OO으로) |

★따옴표는 **낫표(「」)**를 쓴다. 큰따옴표를 쓰면 이 이름을 담는 파이썬 문자열
`name="유튜브 "이건 바로 OO""`가 통째로 깨진다(2026-09-09 실제로 13개 파일이 깨졌다).

## 왜 이 스크립트가 **꼭** 필요한가 (0순위-B)

이름을 코드에서만 바꾸면 안 된다. `tools/seed_*.py`·`spine*_fix_*.py` 5개가
**`s["name"] == 이름`으로 기존 행을 찾는다**. DB가 옛 이름 그대로면:

  · 시드는 "없다"고 판단해 **같은 스파인을 새로 또 만든다**(중복 행)
  · 고침 도구는 "스파인이 없다 — 아무것도 안 했다"로 조용히 지나간다

그래서 **DB 행의 name을 함께 갱신**한다. id는 그대로라 다른 참조(작업 이력·통계)는 안 깨진다.

## 안전한가

라이브 코드는 이름으로 판정하지 않는다 — 전부 `fit_categories`를 본다
(`app.py`의 SUL/CONCEAL/INVENTION_CATEGORIES). 실측으로 확인했다.
이름은 **화면 표시용**이라 바꿔도 조립·게이트 동작은 그대로다.

## 쓰는 법

    python -m tools.spine_rename_youtube            # 미리보기(안 고친다)
    python -m tools.spine_rename_youtube --apply    # 실제로 바꾼다

멱등하다 — 이미 새 이름이면 건너뛴다. 되돌리려면 `--revert --apply`.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shopping_shorts.store import Store  # noqa: E402

DB_PATH = os.environ.get("SHOPPING_SHORTS_DB") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "shopping_shorts", "data", "reference.db")

# ★옛 이름 → 새 이름. 이 파일은 위 일괄교체에서 **제외**된다(표 자신이 바뀌면 뒤집힌다).
_OLD_HIDDEN = "유튜브 " + "은폐형"
_OLD_MISUSE = "유튜브 " + "오용형"
_OLD_INVENT = "유튜브 " + "발명품형"

RENAME = {
    _OLD_HIDDEN: "유튜브 「이건 바로 OO」",
    _OLD_MISUSE: "유튜브 「원래 이렇게 쓰는 거 아닌데」",
    _OLD_INVENT: "유튜브 「OO 개발자도 무릎 탁」",
}


def plan(store, revert=False):
    """무엇을 바꿀지 정한다. [(id, 지금이름, 바꿀이름)] — 바꿀 게 없으면 빈 목록."""
    table = {v: k for k, v in RENAME.items()} if revert else RENAME
    out = []
    for s in store.list_spines():
        new = table.get(s["name"])
        if new and new != s["name"]:
            out.append((s["id"], s["name"], new))
    return out


def apply_rename(store, rows):
    """spine.name만 바꾼다. id·fit_categories·templates는 손대지 않는다."""
    with store._conn() as c:
        for sid, _old, new in rows:
            c.execute("UPDATE spine SET name=? WHERE id=?", (new, sid))
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 바꾼다(없으면 미리보기)")
    ap.add_argument("--revert", action="store_true", help="옛 이름으로 되돌린다")
    ap.add_argument("--db", default=DB_PATH)
    a = ap.parse_args()

    store = Store(a.db)
    rows = plan(store, revert=a.revert)
    if not rows:
        print("바꿀 것 없음 — 이미 %s 이름이다" % ("옛" if a.revert else "새"))
        return 0

    for sid, old, new in rows:
        print("  id=%-4s %s  →  %s" % (sid, old, new))
    if not a.apply:
        print("\n미리보기만 했다. 실제로 바꾸려면 --apply 를 붙여라.")
        return 0

    n = apply_rename(store, rows)
    print("\n%d개 바꿨다. 확인:" % n)
    for s in store.list_spines():
        if s["name"].startswith("유튜브"):
            print("  id=%-4s %-34s 카테고리=%s" % (s["id"], s["name"], s.get("fit_categories")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
