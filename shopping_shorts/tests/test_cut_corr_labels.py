# -*- coding: utf-8 -*-
"""장면 경계 판정(render_bench._real_cut — 경계 앞뒤 프레임 상관 < CUT_CORR_MAX)이 눈 판정 표본에서 잰 정밀도·재현율을 지키나(오류기록 85).

표본 = tools/calcopy/engine/readline_tools/fixtures/cut_corr_labels.json — cutdet 후보 146개를 오푸스가 앞뒤 프레임을 보고
cut(다른 샷·각도·점프컷·디졸브) / same(같은 샷의 움직임·자막만 바뀜·번쩍 효과)로 가른 것(10-25).
문턱을 바꾸면 이 시험이 먼저 깨진다 — 표본을 다시 보고(눈 판정 = 오푸스) 고친다.
원본(C:/숏템_칼카피)이 있으면 몇 개를 실제로 다시 재서 저장한 상관과 같은지도 본다(읽는 법이 바뀌었는데 표본만 옛 값인 일을 막는다).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
FX = ROOT / "tools/calcopy/engine/readline_tools/fixtures/cut_corr_labels.json"


def _rows():
    return json.loads(FX.read_text(encoding="utf-8"))["rows"]


def _pr(rows, th):
    real = lambda r: r["corr"] is None or r["corr"] < th
    tp = sum(1 for r in rows if r["label"] == "cut" and real(r))
    fp = sum(1 for r in rows if r["label"] == "same" and real(r))
    fn = sum(1 for r in rows if r["label"] == "cut" and not real(r))
    return tp / (tp + fp), tp / (tp + fn)


def test_fixture_size():
    rows = _rows()
    assert len(rows) >= 140 and {r["label"] for r in rows} == {"cut", "same"}


def test_rule_meets_measured_precision_recall():
    from tools.calcopy.hybrid.render_bench import CUT_CORR_MAX
    p, r = _pr(_rows(), CUT_CORR_MAX)
    assert p >= 0.94 and r >= 0.96, (p, r)


def test_old_threshold_was_worse():
    """옛 0.6 은 진짜 편집점 절반 이상을 놓쳤다(재현율 0.43) — 이 표본이 그 차이를 실제로 잡는지(검사가 아무것도 안 재는 일 방지)."""
    assert _pr(_rows(), 0.6)[1] < 0.5


def test_remeasure_matches_fixture():
    from tools.calcopy.hybrid import render_bench as RB
    root = Path(json.loads(FX.read_text(encoding="utf-8"))["root"])
    rows = [r for r in _rows() if (root / r["src"]).exists()][::15]
    if not rows:
        pytest.skip("원본 없음")
    for r in rows:
        src = root / r["src"]
        w, h = RB.probe(src)[:2]
        c = RB._cut_corr(src, r["t"], 0, int(h), int(w))
        assert c is not None and abs(c - r["corr"]) < 0.02, (r["src"], r["t"], c, r["corr"])
