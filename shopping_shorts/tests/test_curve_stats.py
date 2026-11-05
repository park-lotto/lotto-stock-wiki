# -*- coding: utf-8 -*-
"""움직임 숫자(analyze.curve_stats) — 30fps 잉크 곡선 → ms·kind·0.1초 폭%. 지침서 §3-1 A(팝 22→109→100% 같은 숫자)."""
from tools.calcopy.engine import analyze as A


def _c(ws, inks, t0=1.0, fps=30):
    return [{"t": round(t0 - 9 / fps + k / fps, 3), "bbox": [0, 100, w, 40] if w else None, "ink": i} for k, (w, i) in enumerate(zip(ws, inks))]


def test_instant_and_pop():
    inst = _c([0] * 9 + [500] * 10, [0] * 9 + [1000] * 10)
    r = A.curve_stats(inst, 1.0, 30)
    assert r["kind"] == "instant" and r["ms"] == 0
    pop = _c([0] * 9 + [110, 300, 545, 520, 500, 500, 500, 500, 500, 500], [0] * 9 + [100, 400, 950, 1000, 1000, 1000, 1000, 1000, 1000, 1000])
    r = A.curve_stats(pop, 1.0, 30)
    assert r["ms"] == 67 and r["kind"].startswith("크기 변화")


def test_exit_replaced_by_next():
    rep = _c([500] * 19, [1000] * 9 + [800] * 10)
    assert A.curve_stats(rep, 1.0, 30, end=True)["kind"].startswith("교체")
