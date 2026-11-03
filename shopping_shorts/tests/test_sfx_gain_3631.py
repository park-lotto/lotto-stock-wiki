# -*- coding: utf-8 -*-
"""#3631 — 효과음 이득: 판 sfx_level.db_below_voice 가 있으면 파일 크기를 재 '목소리 − 그 값'으로, 없으면 옛 gain_db 그대로."""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import render_bench as RB, styles as STY  # noqa: E402


def test_v2_pop_sits_6db_below_voice():
    st = STY.load("잇템로그판_v2")
    f = RB.SFX_DIR / st["sfx_files"]["pop"]
    g = RB.sfx_gain(st, f, -14.5)
    assert abs((RB._SFX_RMS[f] + g) - (-14.5 - 6)) < 0.05


def test_presets_without_level_keep_old_gain():
    st = {"sfx_files": {"gain_db": -8, "pop": "팩01/pop.wav"}}
    assert RB.sfx_gain(st, RB.SFX_DIR / "팩01/pop.wav", -14.5) == -8.0


def test_no_voice_falls_back():
    st = {"sfx_files": {"gain_db": -6}, "sfx_level": {"db_below_voice": 6}}
    assert RB.sfx_gain(st, RB.SFX_DIR / "팩01/pop.wav", math.nan) == -6.0
