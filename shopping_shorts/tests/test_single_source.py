"""원본 찾기 워커(of_worker --single) — 실행기 env 의 single_source 가 지시서 상태까지 와서 둘째 소재를 안 붙인다(10-27: flow 가 env 칸을
정한 것만 옮겨 담아 스위치가 무시됐고, 워커가 소재 2편씩 돌며 이미 찾은 편을 또 찾았다)."""
from tools.calcopy.hybrid import flow as F


def _st():
    return {"ref": "https://www.youtube.com/shorts/LVcGoVjYyPU", "slug": "ititemlog", "sid": "x", "log": []}


def test_setup_keeps_single_source():
    st = _st()
    F.ph_setup_check(st, {"env": {"keys": {}, "missing": [], "single_source": True}}, {}, {})
    assert st["env"].get("single_source") is True


def test_single_source_no_second_slot():
    st = _st()
    st["env"] = {"single_source": True}
    assert F.pick_alt_source(st) is None
    F.f_of_dual_start(st, {}, {}, {})
    assert len(st["slots"]) == 1
