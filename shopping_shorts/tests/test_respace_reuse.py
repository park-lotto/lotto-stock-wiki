# -*- coding: utf-8 -*-
"""계획이 B13(같은 원본 가까운 구간 재사용)을 처음부터 피한다 — material_fit.respace_reuse(판정 = quality_gate.reuse_violations_bench).

10-25 박정수 선크림 키치잇판: 원음 O2 31.77~34.74 뒤에 나레 N5 컷이 같은 원본 29.55~31.09(거리 0.67초 < 3)에 놓여
완성본 관문에서야 B13 × 가 나왔다. 계획(render_bench.timeline)이 아무것도 안 피했다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import material_fit as MF  # noqa: E402
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import common as CM  # noqa: E402
from tools.calcopy.hybrid.quality_gate import reuse_violations_bench  # noqa: E402


def _cut(kind, ss, t0, t1, line, src="a.mp4"):
    return {"kind": kind, "src": src, "ss": ss, "t0": t0, "t1": t1, "dur": round(t1 - t0, 3), "line": line}


def _setup(monkeypatch, tmp_path, starts):
    (tmp_path / "a.mp4").write_bytes(b"x")
    monkeypatch.setattr(RB, "shot_starts", lambda p: starts)
    monkeypatch.setattr(RB, "src_left", lambda p, s: 60.0 - s)
    monkeypatch.setattr(CM, "dur_of", lambda p: 60.0)


def test_같은_샷_안으로_옮겨_B13_을_피한다(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, [20.0, 40.0])          # 샷 [20, 40)
    cuts = [_cut("orig", 31.0, 0.0, 3.0, "O1"), _cut("tts", 28.0, 3.0, 4.5, "N1")]   # 28~29.5 ↔ 31~34 거리 1.5
    assert reuse_violations_bench(cuts, {"a.mp4": 60.0})
    MF.respace_reuse(cuts, tmp_path, log=lambda m: None)
    assert not reuse_violations_bench(cuts, {"a.mp4": 60.0}), cuts
    assert cuts[1]["ss_reuse"] == 28.0 and 20.0 <= cuts[1]["ss"] <= 26.5 + 1e-6
    assert cuts[0]["ss"] == 31.0                          # 원음 컷(입 맞춤)은 안 옮긴다


def test_샷_안에서_못_피하면_그대로_두고_적는다(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, [27.0, 30.0])          # 샷 [27, 30) — 어디로 가도 31 과 3초 안
    cuts = [_cut("orig", 31.0, 0.0, 3.0, "O1"), _cut("tts", 28.0, 3.0, 4.5, "N1")]
    MF.respace_reuse(cuts, tmp_path, log=lambda m: None)
    assert cuts[1]["ss"] == 28.0 and cuts[1]["reuse_unfixed"]


def test_render_bench_timeline_이_respace_를_부른다():
    src = Path(RB.__file__).read_text(encoding="utf-8")
    body = src[src.index("def timeline("):src.index("def pause_targets(")]
    assert "respace_reuse(cuts" in body
