# -*- coding: utf-8 -*-
"""원·화살표 대상 좌표·머무는 시간(fx_target.aim · aim_check, 10-25 사장님 '정확히 어디를 강조할지')."""
import numpy as np

from tools.calcopy.hybrid import fx_target as FX

CUTS = [{"t0": 0.0, "t1": 1.3, "see": "얼굴 근접"}, {"t0": 1.3, "t1": 2.8, "see": "마스크 떼기"}]
ROW = {"line": "N1", "text": "외국인이 있는데요", "t0": 1.4, "t1": 2.3}
VID = lambda t: np.zeros((1920, 1080, 3), np.uint8)   # noqa: E731
WIN = (0, 486, 1080, 1434)


def _ask(boxes, conf=0.9):
    return lambda jpgs, pr: ({"target": "투명해진 마스크", "why": "시험", "boxes": boxes, "confidence": conf}, None)


def test_aim_ok_circle_on_target():
    b = [400, 300, 500, 400]          # 창 좌표 → 화면 y +486
    got = FX.aim(VID, ROW, CUTS, win=WIN, ask=_ask([b, b, b]), channel="ititemlog")
    assert got and got["aim"]["what"] == "투명해진 마스크"
    cx, cy = got["x"] / 100 * 1080, got["y"] / 100 * 1920
    assert 400 <= cx <= 500 and 786 <= cy <= 886 and got["r"] > 0
    assert FX.aim_check([{**ROW, "stickers": [{"kind": "circle_arrow", **got}]}], CUTS, "ititemlog")["ok"]


def test_aim_refuses_gone_moved_big_and_shot_cross():
    b = [400, 300, 500, 400]
    why = []
    assert FX.aim(VID, ROW, CUTS, win=WIN, ask=_ask([b, b, None]), fail=why) is None and "안 보임" in why[0]
    why = []
    assert FX.aim(VID, ROW, CUTS, win=WIN, ask=_ask([b, [700, 300, 800, 400], b]), fail=why) is None and "움직임" in why[0]
    why = []
    big = [0, 0, 900, 900]            # 화면 39% — 벤치 원 대상 상한 10% 초과
    assert FX.aim(VID, ROW, CUTS, win=WIN, ask=_ask([big, big, big]), fail=why) is None and "화면" in why[0]
    why = []
    assert FX.aim(VID, {**ROW, "t0": 1.0, "t1": 2.0}, CUTS, win=WIN, ask=_ask([b, b, b]), fail=why) is None and "샷 경계" in why[0]


def test_aim_check_catches_face_circle_without_target():
    old = {**ROW, "stickers": [{"kind": "circle_arrow", "x": 31.57, "y": 49.53, "how": "yunet", "site": "detected"}]}   # ep12 N1 고치기 전
    r = FX.aim_check([old], CUTS, "ititemlog")
    assert not r["ok"] and "대상 없음" in r["bad"][0]
