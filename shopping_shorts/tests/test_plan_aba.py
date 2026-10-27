"""B16 A-B-A 끼움을 계획에서 바로 돌려준다(렌더+완성본 검사 7분 뒤가 아니라) — 10-27 완주시험 b·c 반려.
주인 = checks.aba_violations(완성본 검사 quality_gate 와 같은 함수)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import runner_ops as R  # noqa: E402


def test_plan_returns_aba_as_jump(tmp_path, monkeypatch):
    from tools.calcopy.hybrid import render_bench
    cuts = [{"t0": 0.0, "t1": 1.0, "src": "A.mp4", "ss": 0, "kind": "tts", "line": "L1"},
            {"t0": 1.0, "t1": 2.0, "src": "B.mp4", "ss": 0, "kind": "tts", "line": "L2"},
            {"t0": 2.0, "t1": 3.0, "src": "A.mp4", "ss": 9, "kind": "tts", "line": "L3"}]
    monkeypatch.setattr(R, "tts_cache_miss", lambda W, v: None)
    monkeypatch.setattr(render_bench, "render", lambda *a, **k: {"timeline": {"cuts": cuts}, "length": 3.0})
    monkeypatch.setattr(R, "plan_sheet", lambda W, v, T: W / "s.jpg")
    monkeypatch.setattr(R, "source_rule_scan", lambda W, T, names: [])
    monkeypatch.setattr(R, "_origin_names", lambda W, v: set())
    out = R.c_plan(tmp_path, {"version": "v"})
    assert any("A-B-A" in j and "A→B→A" in j for j in out["jumps"]), out


def test_plan_marks_problem_made_by_last_fix():
    """고치기가 새로 만든 문제는 표시하고, 지켜야 할 것 전부를 같이 준다(사장님 10-27 '고쳤는데 또 반려할 걸 만든다')."""
    from tools.calcopy.hybrid import flow as F
    st = {}
    a = F._mark_new(st, ["같은 장면 재사용 L9 X@87.60"])
    assert a[0] == "같은 장면 재사용 L9 X@87.60" and a[-1] == F.FIX_ALL
    b = F._mark_new(st, ["A-B-A 끼움 X→Y→X (3)"])
    assert b[0].startswith(F.FIX_NEW)
    assert F._mark_new(st, []) == []


def test_plan_same_after_fix_is_flagged(monkeypatch):
    """고친 답 뒤 계획 지문이 그대로면 맨 앞에 '안 바뀌었다'(10-27 재생: b·c 같은 계획 4~5번)."""
    from tools.calcopy.hybrid import flow as F
    st = {"version": "잇템로그판_v2", "script": {"M": {}, "S": {"lines": []}}, "tries": {}, "log": []}
    monkeypatch.setattr(F.RU, "material_problems", lambda *a, **k: [])
    monkeypatch.setattr(F.RU, "source_rule_static", lambda *a, **k: [])
    monkeypatch.setattr(F, "_origin_names", lambda st: set())
    monkeypatch.setattr(F, "_all_dims", lambda st: {})
    monkeypatch.setattr(F, "_ar", lambda v: (9, 16))
    monkeypatch.setattr(F, "_fix_review", lambda st, why, sheet, rid: {"id": rid, "why": why})
    p = {"plan": {"over": "컷 넘침", "sig": "S1", "sheet": None}}
    r1 = F.ph_plan_got(st, p, {}, {})
    r2 = F.ph_plan_got(st, p, {}, {})
    assert F.PLAN_SAME not in r1["review"][0]["why"] and r2["review"][0]["why"].startswith(F.PLAN_SAME)
