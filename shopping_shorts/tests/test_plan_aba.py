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
