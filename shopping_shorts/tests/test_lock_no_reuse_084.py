# -*- coding: utf-8 -*-
"""고조 줄 장면 고정이 근거 컷을 다 쓴 뒤 첫 컷을 다시 쓰지 않는다(2026-10-03 사장님 "같은 카드가 자주 쓰인다")."""
import inspect
from shopping_shorts import story_writer as sw


def test_lock_fallback_does_not_reuse_first_cut():
    src = inspect.getsource(sw)
    i = src.index("_locked = 0")
    body = src[i:src.index('n["locked_lines"] = _locked', i)]
    assert "or allowed[:1]" not in body
    assert "_taken.update(mine)" in body and "continue" in body
