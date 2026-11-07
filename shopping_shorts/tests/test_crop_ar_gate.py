# -*- coding: utf-8 -*-
"""11-05 얜샷템 회원 편: 두 칸 비교 원본의 왼쪽 칸만 crop [100,0,606,1080](0.56)으로 잘랐는데 창이 1:1 → 엔진(cut_crop, #5442 수리)이
[0,0,1080,1080]로 넓혀 오른쪽 칸 테두리가 완성본에 들어갔다(자동 검사 통과). 렌더 전 계획 관문 '자를 칸 비율'이 그 줄을 알린다 — 넓히는 계산은 cut_crop 그대로."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402


def _case(tmp_path, monkeypatch, crop):
    (tmp_path / "v.mp4").write_bytes(b"x")
    monkeypatch.setattr(RB, "_src_wh", lambda src: (1920, 1080))
    st = {"frame": {"kind": "window", "window": [0, 420, 1080, 1080]}}
    T = {"cuts": [{"line": "L6", "src": "v.mp4", "ss": 66.2, "crop": crop, "dur": 2.0}]}
    return RB.crop_ar_gate(T, {"cand_dir": str(tmp_path)}, st)


def test_portrait_crop_on_square_window_is_reported(tmp_path, monkeypatch):
    out = _case(tmp_path, monkeypatch, [100, 0, 606, 1080])
    assert len(out) == 1 and "L6" in out[0] and "[0, 0, 1080, 1080]" in out[0]


def test_crop_at_window_ratio_passes(tmp_path, monkeypatch):
    assert _case(tmp_path, monkeypatch, [100, 0, 1080, 1080]) == []
    assert _case(tmp_path, monkeypatch, "face") == []


def test_gate_is_in_plan_gate_list():
    import inspect
    assert "crop_ar_gate(T, M, st)" in inspect.getsource(RB.timeline_gates)
