# -*- coding: utf-8 -*-
"""#1963 한정수 — '원본 박힌 자막은 흐림 말고 확대로'를 원했는데 재료 검사 ZOOM_MIN_H(원본 높이 95%)가 막아 회원 Claude 가 rules.py 를 고쳤다.
주인 rules.zoom_floor — 기본은 확대 1.0, 회원이 요청한 컷(zoom: true)은 1.67배까지 · 원본 540px 아래로는 안 된다(화질 하한)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import rules as RU  # noqa: E402


def _probs(cut, dims=(1920, 1080)):
    M = {"cuts": {"L1": [{"src": "a.mp4", "ss": 1.0, **cut}]}}
    return [p for p in RU.material_problems(M, {"a.mp4"}, set(), {"a.mp4": dims}, None) if "확대" in p]


def test_default_still_one_x():
    assert _probs({"crop": [0, 0, 1500, 800]})                      # 1.35배 — 회원 요청 없으면 그대로 막는다
    assert "zoom" in _probs({"crop": [0, 0, 1500, 800]})[0]          # 막는 글이 회원 요청 길을 알려 준다


def test_member_zoom_allowed_to_floor():
    assert not _probs({"crop": [0, 0, 1500, 800], "zoom": True})     # 1.35배 = 회원 요청이면 통과
    assert _probs({"crop": [0, 0, 900, 500], "zoom": True})          # 2.16배 = 1.67배 넘음


def test_quality_floor_px_on_small_source():
    assert _probs({"crop": [0, 0, 900, 500], "zoom": True}, dims=(1280, 720))      # 720 원본: 540px 아래로 못 자른다
    assert not _probs({"crop": [0, 0, 960, 540], "zoom": True}, dims=(1280, 720))
