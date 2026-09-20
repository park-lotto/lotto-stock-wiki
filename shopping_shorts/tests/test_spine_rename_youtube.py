# -*- coding: utf-8 -*-
"""유튜브 스파인 이름 바꾸기(2026-09-09) — 옛 행을 **찾아 갱신**하는지 본다.

★왜 테스트가 필요한가: 코드에서만 이름을 바꾸면 `tools/seed_*.py`가
`s["name"] == 이름`으로 옛 행을 못 찾아 **같은 스파인을 새로 또 만든다**(중복 행).
그래서 (1) id가 유지되는지 (2) 멱등한지 (3) fit_categories가 안 다치는지
(4) ★시드 도구가 바뀐 이름으로 그 행을 찾는지를 검사한다.

⚠️ 이 파일도 일괄교체 대상에서 **제외**된다 — 옛 이름을 그대로 들고 있어야
   "옛 이름으로 심고 → 새 이름으로 바뀌는지"를 검사할 수 있다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shopping_shorts.store import Store            # noqa: E402
from tools import spine_rename_youtube as R        # noqa: E402

# 옛 이름(문자열을 쪼개 둔다 — 일괄교체 스크립트가 다시 돌아도 안 잡히게)
OLD_HIDDEN = "유튜브 " + "은폐형"
OLD_MISUSE = "유튜브 " + "오용형"
OLD_INVENT = "유튜브 " + "발명품형"

NEW_HIDDEN = "유튜브 「이건 바로 OO」"
NEW_MISUSE = "유튜브 「원래 이렇게 쓰는 거 아닌데」"
NEW_INVENT = "유튜브 「OO 개발자도 무릎 탁」"


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def _seed_old(st):
    """옛 이름으로 3종을 심는다(라이브 55·56·60과 같은 모양)."""
    ids = {}
    for name, cats in ((OLD_HIDDEN, ["제품정체형"]),
                       (OLD_MISUSE, ["오용형"]),
                       (OLD_INVENT, ["발명품형"])):
        ids[name] = st.add_spine(name=name, fit_categories=cats, status="approved")
    return ids


def test_rename_keeps_id_and_categories(tmp_path):
    """이름만 바뀌고 id·fit_categories는 그대로다 — 다른 참조가 안 깨진다."""
    st = _store(tmp_path)
    ids = _seed_old(st)
    rows = R.plan(st)
    assert len(rows) == 3, "3종을 다 찾아야 한다 — 찾은 것: %r" % (rows,)
    R.apply_rename(st, rows)

    got = {s["id"]: s for s in st.list_spines()}
    assert got[ids[OLD_HIDDEN]]["name"] == NEW_HIDDEN
    assert got[ids[OLD_MISUSE]]["name"] == NEW_MISUSE
    assert got[ids[OLD_INVENT]]["name"] == NEW_INVENT
    # ★카테고리는 코드가 판정에 쓰는 값이다 — 여기가 다치면 조립이 통째로 죽는다
    assert got[ids[OLD_MISUSE]]["fit_categories"] == ["오용형"]
    assert got[ids[OLD_HIDDEN]]["fit_categories"] == ["제품정체형"]
    assert got[ids[OLD_INVENT]]["fit_categories"] == ["발명품형"]


def test_rename_is_idempotent(tmp_path):
    """두 번 돌려도 새 행이 안 생긴다(시드가 중복을 만드는 사고를 막는다)."""
    st = _store(tmp_path)
    _seed_old(st)
    R.apply_rename(st, R.plan(st))
    before = len(st.list_spines())

    again = R.plan(st)
    assert again == [], "이미 새 이름인데 또 바꾸려 한다 — 멱등이 아니다"
    R.apply_rename(st, again)
    assert len(st.list_spines()) == before, "행이 늘었다 — 중복 생성"


def test_revert_restores_old_names(tmp_path):
    """--revert로 되돌릴 수 있다."""
    st = _store(tmp_path)
    ids = _seed_old(st)
    R.apply_rename(st, R.plan(st))
    R.apply_rename(st, R.plan(st, revert=True))
    got = {s["id"]: s["name"] for s in st.list_spines()}
    assert got[ids[OLD_HIDDEN]] == OLD_HIDDEN
    assert got[ids[OLD_INVENT]] == OLD_INVENT


def test_plan_ignores_other_spines(tmp_path):
    """유튜브 3종 말고는 건드리지 않는다."""
    st = _store(tmp_path)
    _seed_old(st)
    other = st.add_spine(name="가족갈등 반전형", fit_categories=["홈템"], status="approved")
    R.apply_rename(st, R.plan(st))
    got = {s["id"]: s["name"] for s in st.list_spines()}
    assert got[other] == "가족갈등 반전형", "무관한 스파인이 바뀌었다"


def test_seed_tools_find_renamed_rows(tmp_path):
    """★이 테스트가 핵심 — 이름을 바꾼 뒤 시드 도구가 **그 행을 찾는다**.

    seed_style_youtube._upsert는 `s["name"] == spec["name"]`으로 찾는다.
    코드의 spec 이름과 DB의 이름이 어긋나면 새 행을 만든다(중복).
    """
    from tools import seed_style_youtube as S
    st = _store(tmp_path)
    ids = _seed_old(st)
    R.apply_rename(st, R.plan(st))

    hit = [s for s in st.list_spines() if s["name"] == S.HIDDEN["name"]]
    assert len(hit) == 1, "시드가 은폐형 행을 못 찾는다 → 중복 생성된다"
    assert hit[0]["id"] == ids[OLD_HIDDEN], "옛 행이 아니라 다른 행을 잡았다"

    hit2 = [s for s in st.list_spines() if s["name"] == S.MISUSE["name"]]
    assert len(hit2) == 1 and hit2[0]["id"] == ids[OLD_MISUSE]


def test_invention_seed_finds_renamed_row(tmp_path):
    """발명품형 시드도 같은 함정에 안 빠진다."""
    from tools import seed_spine_invention as I
    st = _store(tmp_path)
    ids = _seed_old(st)
    R.apply_rename(st, R.plan(st))

    hit = [s for s in st.list_spines() if s["name"] == I.SPEC["name"]]
    assert len(hit) == 1, "발명품형 시드가 행을 못 찾는다 → 중복 생성된다"
    assert hit[0]["id"] == ids[OLD_INVENT]
