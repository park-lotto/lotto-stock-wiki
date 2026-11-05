# -*- coding: utf-8 -*-
"""말풍선 층(관제 319 11-06) — 스냅봤니 벤치 4편 말풍선 31줄(검정 둥근 상자 + 색 글 + 기울기)을 render_bench 가 판 frame.bubble 칸으로 굽는다.
실측 근거: C:/t/snapfix_jev/bubble_measure.json(measure_bub.py) — 상자 #000000·반지름 13·여백 23/17·BMJUA 72px·기울기 중앙 +4.7도(반시계)."""
import json

import numpy as np
import pytest

from tools.calcopy.hybrid import render_bench as RB
from tools.calcopy.hybrid.common import ROOT, StageError

BB = {"font": "BMJUA.ttf", "px": 72, "rot": 4.7, "box": {"rgb": "#000000", "alpha": 1.0, "radius": 13, "pad_x": 23, "pad_y": 17},
      "ring": {"px": 6, "color": "#FFFFFF"}, "colors": {"yellow": "#FCE61C", "green": "#3CF141"}}
T = {"lines": {"O1": [0.0, 3.9], "O2": [3.9, 7.15]}, "end": 7.15}


def _S(b):
    return {"lines": [{"id": "O1", "kind": "orig"}, {"id": "O2", "kind": "orig", "bubbles": b}]}


def test_plan_absolute_time_and_defaults():
    out = RB.bubble_plan(_S([["어? 안녕?", 0.5, 1.9, {"x": 600, "y": 700, "color": "yellow"}]]), T, {"frame": {"bubble": BB}})
    assert out == [{"line": "O2", "t0": 4.4, "t1": 5.8, "text": "어? 안녕?", "x": 600, "y": 700, "color": "#FCE61C", "rot": 4.7, "style": "box"}]


def test_plan_none_when_no_bubbles_keeps_other_pans():
    assert RB.bubble_plan({"lines": [{"id": "O1", "kind": "orig"}]}, T, {"frame": {}}) == []


def test_plan_refuses_bubbles_without_pan_slot():
    with pytest.raises(StageError):
        RB.bubble_plan(_S([["어?", 0.1, 1.0, {"x": 1, "y": 2}]]), T, {"frame": {}})
    with pytest.raises(StageError):          # 자리 없음
        RB.bubble_plan(_S([["어?", 0.1, 1.0, {}]]), T, {"frame": {"bubble": BB}})


def test_png_box_text_and_tilt(tmp_path):
    from PIL import Image
    import cv2
    b = {"text": "나만 의자 업떠", "x": 540, "y": 700, "color": "#FCE61C", "rot": 6.0, "style": "box"}
    x0, y0 = RB.bubble_png(b, BB, tmp_path / "b.png")
    a = np.array(Image.open(tmp_path / "b.png").convert("RGBA")).astype(int)
    h, w = a.shape[:2]
    assert abs((x0 + w / 2) - 540) <= 1 and abs((y0 + h / 2) - 700) <= 1
    opaque = a[..., 3] > 250
    black = opaque & (a[..., :3].max(2) < 20)
    yel = opaque & (np.abs(a[..., :3] - [0xFC, 0xE6, 0x1C]).sum(2) < 60)
    assert black.sum() > 2 * yel.sum() > 0                   # 상자가 글보다 넓다
    ys, xs = np.nonzero(yel)
    vx, vy, _, _ = cv2.fitLine(np.float32(np.column_stack([xs, ys])), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
    ang = -np.degrees(np.arctan2(vy, vx))
    ang = ang - 180 if ang > 90 else ang + 180 if ang < -90 else ang
    assert 4.5 <= ang <= 7.5                                  # + = 반시계(오른쪽이 올라감) — 벤치 실측 부호


def test_snap_pan_has_measured_bubble_slot():
    st = json.loads((ROOT / "tools/calcopy/hybrid/styles/스냅봤니판.json").read_text(encoding="utf-8"))
    B = st["frame"]["bubble"]
    assert B["box"]["rgb"] == "#000000" and B["box"]["radius"] == 13 and B["px"] == 72 and abs(B["rot"] - 4.7) < 0.01
    assert set(B["colors"]) == {"yellow", "green", "pink", "blue", "sky"}
