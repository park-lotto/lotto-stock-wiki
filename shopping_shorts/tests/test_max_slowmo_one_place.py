# -*- coding: utf-8 -*-
"""슬로우모션 상한은 config.MAX_SLOWMO 한 곳 (관제 020, 2026-10-01 사장님 "제일 심플하게").
고치기 전: video_assemble 1.15·scene_play.js 1.15 각자 숫자 → 이 검사가 FAIL 나야 유효하다."""
import io
import os
import re

from shopping_shorts import config, video_assemble as va

_JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "scene_play.js")


def test_render_reads_config():
    assert va._MAX_SLOWMO == config.MAX_SLOWMO == 1.2


def test_js_has_no_own_number():
    js = io.open(_JS, encoding="utf-8").read()
    assert "const MAX_SLOWMO" not in js
    assert "maxSlowmo()" in js and "DATA.max_slowmo" in js


def test_short_cut_slows_without_freeze():
    # 2초 대사에 1.8초 컷: 1.11배 늦춤 → 정지 0 (사장님 10-01 질문의 예)
    play, freeze = va._speed_and_freeze(1.8, 2.0)
    assert abs(play - 2.0) < 1e-6 and freeze == 0
    # 상한 넘으면(1.5초 컷·2초 대사) 1.2배까지만 늦추고 나머지 정지
    play, freeze = va._speed_and_freeze(1.5, 2.0)
    assert abs(play - 1.8) < 1e-6 and abs(freeze - 0.2) < 1e-6


def test_scene_lab_data_carries_max_slowmo():
    src = io.open(os.path.join(os.path.dirname(_JS), "..", "app.py"), encoding="utf-8").read()
    assert re.search(r'"max_slowmo":\s*float\(config\.MAX_SLOWMO\)', src)
