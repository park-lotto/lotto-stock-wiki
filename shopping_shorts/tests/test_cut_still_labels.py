# -*- coding: utf-8 -*-
"""멈춤 판정(quality_gate.still_spans → spans_from) — 렌더 전 관문 ⑦(render_bench.cut_still_gate)과 완성본 '화면 멈춤 없음'(freezes)이 같이 쓴다.

표본 = fixtures/cut_still_labels.json — 원본 컷 51개를 오푸스가 still/moving 으로 가른 것(10-25). 문턱을 바꾸면 이 시험이 먼저 깨진다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import quality_gate as QG  # noqa: E402

FX = ROOT / "shopping_shorts/tests/fixtures/cut_still_labels.json"


def _rows():
    return json.loads(FX.read_text(encoding="utf-8"))["rows"]


def _pr(rows, fn):
    tp = sum(1 for r in rows if r["label"] == "still" and fn(r))
    fp = sum(1 for r in rows if r["label"] == "moving" and fn(r))
    miss = sum(1 for r in rows if r["label"] == "still" and not fn(r))
    return tp / (tp + fp), tp / (tp + miss)


def _rule(r):
    return bool(QG.spans_from(r["d1"], r["p99"]))


def test_fixture():
    rows = _rows()
    assert len(rows) >= 50 and sum(r["label"] == "still" for r in rows) >= 12


def test_rule_precision_recall():
    p, r = _pr(_rows(), _rule)
    assert p >= 0.9 and r >= 0.95, (p, r)


def test_halves():
    rows = _rows()
    for half in (rows[0::2], rows[1::2]):
        p, r = _pr(half, _rule)
        assert p >= 0.85 and r >= 0.95, (p, r)


def test_mean_diff_rule_was_worse():
    """진단 G-9 안(이웃 평균 차 < 1.5 가 1초)은 말하는 얼굴까지 잡아 정밀도가 낮다 — 표본이 그 차이를 실제로 가르는지."""
    def mean_rule(r):
        c = b = 0
        for x in r["d1"]:
            c = c + 1 if x < 1.5 else 0
            b = max(b, c)
        return b >= 29
    assert _pr(_rows(), mean_rule)[0] < 0.6


def test_freezes_uses_same_judgment():
    import numpy as np
    fr = np.zeros((40, 16, 108), np.int16)
    fr[20:] = 50                          # 0~0.67초 정지 → 바뀜 → 정지
    assert QG.still_spans(fr) == QG.spans_from(*QG.still_series(fr))
    assert QG.still_spans(fr)


def test_remeasure_matches_fixture():
    import subprocess
    import numpy as np
    rows = [r for r in _rows() if Path(r["src"]).exists()][::10]
    if not rows:
        pytest.skip("원본 없음")
    for r in rows:
        n = round(r["dur"] * 30)
        vf = (f"crop={r['crop'][2]}:{r['crop'][3]}:{r['crop'][0]}:{r['crop'][1]}," if r.get("crop") else "") + "fps=30,scale=108:-2,format=gray"
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{r['ss']:.3f}", "-i", r["src"], "-an", "-vf", vf, "-frames:v", str(n), "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        h = next(h for h in range(8, 400) if len(raw) % (108 * h) == 0 and abs(len(raw) // (108 * h) - n) <= 3)
        d1, p99 = QG.still_series(np.frombuffer(raw, np.uint8).reshape(-1, h, 108).astype(np.int16))
        assert bool(QG.spans_from(d1, p99)) == bool(QG.spans_from(r["d1"], r["p99"])), r["src"]
