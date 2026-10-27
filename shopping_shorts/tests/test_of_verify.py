"""받은 원본 실제 장면 확인(flow.f_of_verify_got) — 썸네일로 고른 '같은 촬영분'이 실제 장면에서 다르면 뺀다(10-27 of_worker 3편 중 2편 다른 사람)."""
import pytest
from tools.calcopy.hybrid import flow as F


def _st():
    o = lambda i, how: {"id": i, "how": how, "files": [{"name": f"{i}.mp4", "dur": 20}]}
    st = {"log": [], "tries": {}, "origins": [o("A", "렌즈 같은 촬영분"), o("B", "렌즈 같은 촬영분"), o("P", "같은 제품 다른 해외 반응")]}
    st["_verify"] = {"keep": ["A", "B", "P"], "chk": ["A", "B"], "rows": ["A", "B"]}
    return st


def test_drops_not_same_keeps_peer():
    st = _st()
    F.f_of_verify_got(st, {}, {"of_verify": {"same": [2], "why": "1 다른 사람"}}, {})
    assert [o["id"] for o in st["origins"]] == ["B", "P"]


def test_all_dropped_peer_remains():
    st = _st()
    F.f_of_verify_got(st, {}, {"of_verify": {"same": [], "why": "둘 다 다름"}}, {})
    assert [o["id"] for o in st["origins"]] == ["P"]


def test_nothing_left_stops():
    st = _st()
    st["origins"] = st["origins"][:2]
    st["_verify"]["keep"] = ["A", "B"]
    with pytest.raises(F._Stop):
        F.f_of_verify_got(st, {}, {"of_verify": {"same": [], "why": "다름"}}, {})


def test_peer_only_skips_verify():
    st = _st()
    st["origins"] = [st["origins"][2]]
    r = F._of_verify_ask(st, st["origins"], st["origins"][0]["files"])
    assert r.get("goto") == "f_product_sheet"
