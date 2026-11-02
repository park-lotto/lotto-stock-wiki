"""막혔을 때 빠져나가는 길(관제 304): 앞 단계로·권고 넘기기·직접 만들기·같은 실패만 세기."""
import os

import pytest

from tools.calcopy.hybrid import flow as F
from tools.calcopy.hybrid import render_bench as RB


def _st(stage="plan", **k):
    return {"version": "키치잇판", "log": [], "tries": {"plan": 9}, "phase": "task_got", "_task": {"id": "task_1", "stage": stage, "why": "x", "fix": "y", "retry": stage}, **k}


def _go(st, **a):
    return F.ph_task_got(st, {}, {"task_1": {"action": a.pop("action"), **a}}, {})


def test_back_to_passed_stage_only():
    st = _st()
    assert _go(st, action="back", to="script") == {"goto": "script"}
    assert "plan" in st["tries"]
    with pytest.raises(F._Stop):
        _go(_st(stage="script"), action="back", to="check")      # 아직 안 간 단계로는 못 간다


def test_submit_goes_to_result_judgement():
    st = _st(auto={"ok": False})
    assert _go(st, action="submit", note="직접 만듦") == {"goto": "check"}


def test_waive_plan_and_check():
    st = _st()
    assert _go(st, action="waive") == {"goto": "render"} and st["waive_gate"]
    st = _st(stage="check", auto={"ok": False, "rows": [{"what": "B14 효과음", "ok": False}]}, look={"ok": False, "problems": []})
    assert _go(st, action="waive") == {"goto": "deliver"} and st["look_left"]


def test_waive_cannot_pass_red_line():
    st = _st(stage="script", _script_try={"S": {}, "M": {}, "causes": ["forbid_must"]})      # 금지선(질병·금액) — 11-03 부터 후기 숫자(claims)는 권고
    with pytest.raises(F._Stop):
        _go(st, action="waive")
    st = _st(stage="script", _script_try={"S": {"a": 1}, "M": {}, "causes": ["form"]})
    assert _go(st, action="waive")["then"] == "sign" and st["script"]["S"] == {"a": 1}


def test_same_failure_counted_different_failure_is_progress():
    st = {"version": "키치잇판", "log": [], "tries": {}, "phase": "plan"}
    for _ in range(F.TASK_PER_KEY):
        assert F._task(st, F._Stop("같은 이유", "x", retry="plan", detail="A"), "plan_got", "plan")
    assert F._task(st, F._Stop("같은 이유", "x", retry="plan", detail="A"), "plan_got", "plan") is None
    assert F._task(st, F._Stop("같은 이유", "x", retry="plan", detail="B"), "plan_got", "plan")


def test_waive_flag_reaches_render_do():
    st = {"version": "v", "log": [], "tries": {}, "waive_gate": True, "phase": "render"}
    do = [{"id": "r", "cmd": "render"}, {"id": "w", "cmd": "write_doc"}]
    F._out(st, "execute", "render", do=do)
    assert do[0]["waive"] is True and "waive" not in do[1]


def test_gate_stop_waive(monkeypatch):
    with pytest.raises(RB.GateError):
        RB.gate_stop([("x", ["문제"])])
    monkeypatch.setenv("SHORTEM_WAIVE_GATE", "1")
    assert RB.gate_stop([("x", ["문제"])]) is None


def test_material_before_script_goes_to_script():
    from tools.calcopy.hybrid import flow as F
    import inspect
    src = inspect.getsource(F)
    assert 'if names and not st.get("script"):' in src and 'st["material"] = {"files": [{"name": n} for n in names]}' in src
