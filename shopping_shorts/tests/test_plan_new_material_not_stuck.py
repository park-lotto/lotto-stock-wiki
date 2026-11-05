"""11-05 김미향 #7764: 장면 검수 3번째 답에 새 재료를 보내도 '같은 원인 3번 연속' 멈춤이 재료 받기보다 먼저 걸려 재료가 버려지고 같은 반려가 반복됐다."""
import pytest

from tools.calcopy.hybrid import flow as F


def _st():
    return {"version": "v1", "tries": {"plan": 2}, "log": [], "research": {}, "bench": {"id": "b"}, "origin": {"id": "o", "files": [{"name": "o.mp4"}]},
            "script": {"S": {"lines": []}, "M": {"cuts": {"L1": [{"src": "o.mp4", "ss": 1.0}]}}}, "material": {"files": []},
            "_plan_over": ["컷이 원본 샷보다 길다: x"], "redo_hist": {"plan": [["cut_len"], ["cut_len"]]}}


def test_new_material_on_third_answer_is_taken_not_stuck(monkeypatch):
    st = _st()
    newM = {"cuts": {"L1": [{"src": "o.mp4", "ss": 5.0}]}}
    monkeypatch.setattr(F, "_reply", lambda rp, k, need: {"재료": newM})
    monkeypatch.setattr(F, "_take_fix", lambda st, r: st["script"].__setitem__("M", r["재료"]) or r["재료"])
    monkeypatch.setattr(F, "_plan_causes", lambda xs: ["cut_len"])
    r = F.ph_plan_look(st, {}, {}, {})
    assert r["do"][0]["cmd"] == "write_doc" and r["do"][0]["files"]["v1/재료.json"] == newM


def test_same_material_third_time_still_stuck(monkeypatch):
    st = _st()
    same = st["script"]["M"]
    monkeypatch.setattr(F, "_reply", lambda rp, k, need: {"재료": same})
    monkeypatch.setattr(F, "_take_fix", lambda st, r: r["재료"])
    monkeypatch.setattr(F, "_plan_causes", lambda xs: ["cut_len"])
    with pytest.raises(F._Stop):
        F.ph_plan_look(st, {}, {}, {})
