"""10-31 글로스 편 실데이터: 계획과 완성본이 B13 을 같은 함수로 잰다 — L1↔L4 를 계획에서 잡는다."""
from pathlib import Path

from tools.calcopy.hybrid import quality_gate as QG, runner_ops as RO


def test_plan_catches_what_final_gate_caught(tmp_path, monkeypatch):
    v = "판"
    (tmp_path / "doc" / v).mkdir(parents=True)
    (tmp_path / "doc" / v / "재료.json").write_text('{"cand_dir": "%s"}' % tmp_path.as_posix(), encoding="utf-8")
    (tmp_path / "a.mp4").write_bytes(b"x")
    import tools.calcopy.hybrid.styles as ST
    monkeypatch.setattr(ST, "load", lambda n: {})
    import tools.calcopy.hybrid.common as C
    monkeypatch.setattr(C, "dur_of", lambda p: 60.0)
    T = {"cuts": [{"src": "a.mp4", "ss": 0.30, "t0": 0.0, "t1": 2.1, "line": "L1"}, {"src": "b.mp4", "ss": 0, "t0": 2.1, "t1": 3.0, "line": "L2"},
                  {"src": "a.mp4", "ss": 4.73, "t0": 3.0, "t1": 5.05, "line": "L4"}]}
    out = RO._plan_reuse(tmp_path, v, T)
    assert out and "L1" in out[0] and "L4" in out[0] and "재료_더찾기" in out[0]
