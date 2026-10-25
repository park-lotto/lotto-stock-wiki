# -*- coding: utf-8 -*-
"""렌더 전 관문 ⑤ 컷 길이(render_bench.cut_length_gate) — 눈 판정 표본(fixtures/cut_length_labels.json)에서 정밀도·재현율.

컷 하나가 통째로 MIN_PIECE_SEC(0.4초)보다 짧으면 멈춘다(관문 ③ short_pieces 와 같은 상수).
관문 ③은 컷 '안' 경계만 봐서 이런 컷을 못 잡았다 — 그것도 여기서 확인한다(검사가 아무것도 안 재는 일 방지).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import render_bench as RB  # noqa: E402

FX = ROOT / "shopping_shorts/tests/fixtures/cut_length_labels.json"


def _rows():
    return json.loads(FX.read_text(encoding="utf-8"))["rows"]


def _T(rows):
    t, cuts = 0.0, []
    for r in rows:
        cuts.append({"line": r["line"], "src": r["src"], "ss": r["ss"], "frames": r["frames"], "t0": t, "t1": t + r["frames"] / RB.FPS})
        t += r["frames"] / RB.FPS
    return {"cuts": cuts}


def test_fixture():
    rows = _rows()
    assert len(rows) >= 20 and {r["label"] for r in rows} == {"flash", "ok"}


def test_rule_precision_recall():
    rows = _rows()
    hit = {int(b.split()[2]) for b in RB.cut_length_gate(_T(rows))}
    tp = sum(1 for k, r in enumerate(rows) if r["label"] == "flash" and k in hit)
    fp = sum(1 for k, r in enumerate(rows) if r["label"] == "ok" and k in hit)
    fn = sum(1 for k, r in enumerate(rows) if r["label"] == "flash" and k not in hit)
    assert tp / (tp + fp) == 1.0 and tp / (tp + fn) == 1.0, (tp, fp, fn)


def test_old_gate_missed_whole_short_cut():
    """관문 ③(컷 안 경계 조각)은 경계가 없는 0.3초 컷을 통과시켰다."""
    for r in _rows():
        if r["label"] == "flash":
            assert RB.short_pieces([], r["ss"], r["ss"] + r["frames"] / RB.FPS) == []


def test_same_constant_as_piece_gate():
    one = {"cuts": [{"line": "N1", "src": "a.mp4", "ss": 0.0, "frames": round(RB.MIN_PIECE_SEC * RB.FPS) - 1, "t0": 0, "t1": 1}]}
    ok = {"cuts": [{"line": "N1", "src": "a.mp4", "ss": 0.0, "frames": round(RB.MIN_PIECE_SEC * RB.FPS), "t0": 0, "t1": 1}]}
    assert RB.cut_length_gate(one) and not RB.cut_length_gate(ok)
