# -*- coding: utf-8 -*-
"""출처 줄 자리 주인 = render_bench.credit_xy(C, bb, left) — frame_png(틀 안)·render_base(in_window) 가 같이 부른다(11-07 썰반장, Jev q_credit2 통과).
기본은 옛 그대로(틀 안 가운데 · in_window 왼쪽), align left 면 x 가 잉크 왼쪽 끝."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402

BB = (3, 10, 203, 50)      # textbbox 꼴(왼·위·오른·아래)


def test_default_center_same_as_old():
    C = {"ink_top": 1535}
    assert RB.credit_xy(C, BB) == (RB.W // 2 - (BB[2] - BB[0]) // 2 - BB[0], 1535 - BB[1])
    assert RB.credit_xy({"center": 1500}, BB) == (RB.W // 2 - 100 - 3, 1500 - 30)


def test_in_window_left_same_as_old():
    C = {"in_window": True, "x": 112, "cy": 470}
    assert RB.credit_xy(C, BB, left=150) == (150 - BB[0], 470 - (BB[1] + BB[3]) // 2)


def test_align_left_ink_at_x():
    x, y = RB.credit_xy({"align": "left", "x": 56, "ink_top": 1483}, BB)
    assert (x + BB[0], y + BB[1]) == (56, 1483)


def test_sseolbanjang_credit_ink_left_56():
    """실제 글꼴로 틀을 그려 출처 잉크 왼쪽 끝·위가 벤치(x56·y1483) ±3px 인지 잰다(틀 그림 = 결과물)."""
    import numpy as np
    from PIL import Image
    from tools.calcopy.hybrid import styles as ST
    out = Path(__file__).with_name("_tmp_credit_frame.png")
    try:
        RB.frame_png({"title_lines": [[["가", None]], [["나", None]]], "source_label": "© 샤레이드(Charade, 1963)"}, ST.load("썰반장판"), out)
        a = np.asarray(Image.open(out).convert("RGB"))[1460:1560].max(axis=2) > 128
        ys, xs = np.nonzero(a)
        assert abs(int(xs.min()) - 56) <= 3 and abs(int(ys.min()) + 1460 - 1483) <= 3, (xs.min(), ys.min() + 1460)
    finally:
        out.unlink(missing_ok=True)
