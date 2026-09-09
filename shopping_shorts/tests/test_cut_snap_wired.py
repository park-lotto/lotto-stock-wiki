# -*- coding: utf-8 -*-
"""★배선 테스트 — extract_script가 _snap_to_cuts를 **실제로 부르는가**.

함수만 만들고 호출부에 안 붙이는 사고가 이 코드베이스에서 반복됐다
(memory: 배선은층마다·가짜단언4번 / 배선테스트_함수이름지어냄).
그래서 AST로 '호출된다'를 직접 검사한다 — 문자열 검색은 주석에도 걸린다.
"""
import ast
import io
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "script_extract.py"


def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def test_extract_script가_snap을_호출한다():
    tree = ast.parse(io.open(SRC, encoding="utf-8").read())
    fn = _fn(tree, "extract_script")
    assert fn is not None, "extract_script가 없다 — 이름이 바뀌었으면 이 테스트부터 고쳐라"
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_snap_to_cuts" in called, (
        "extract_script가 _snap_to_cuts를 부르지 않는다 — 함수만 있고 배선이 없다")


def test_snap이_seg_id부여_전에_돈다():
    """seg_id 부여(_assign_seg_ids) 뒤에 붙이면 경계만 바뀌고 모션레벨이 어긋난다."""
    tree = ast.parse(io.open(SRC, encoding="utf-8").read())
    fn = _fn(tree, "extract_script")
    order = [n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id in ("_snap_to_cuts", "_assign_seg_ids", "_merge_too_short")]
    assert "_snap_to_cuts" in order and "_assign_seg_ids" in order
    assert order.index("_snap_to_cuts") < order.index("_assign_seg_ids"), \
        f"순서가 틀렸다: {order}"
    assert order.index("_merge_too_short") < order.index("_snap_to_cuts"), \
        f"병합이 스냅보다 먼저여야 한다: {order}"
