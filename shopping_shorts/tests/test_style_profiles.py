# -*- coding: utf-8 -*-
"""채널 스타일 주입 (대본퀄 v6) — 블록 내용·스위치·실제 배선."""
import os
from unittest.mock import patch

from shopping_shorts import style_profiles
from shopping_shorts.edit_plan import _scene_first_candidates


def test_maison_block_has_fewshot_and_guide():
    b = style_profiles.style_block("maison")
    assert "스타일 예시" in b and "158만 회" in b
    assert "소리 질렀어요" in b            # few-shot 원문이 전문으로 실린다
    assert "인물을 통과한다" in b          # 가이드
    assert "CTA 규칙(명분+보상형)" in b    # CTA는 우리 규칙 우선


def test_switch_off_and_unknown():
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert style_profiles.active_style() is None
        assert style_profiles.style_block() == ""
    with patch.dict(os.environ, {"SCRIPT_STYLE": "0"}):
        assert style_profiles.style_block() == ""
    assert style_profiles.style_block("모르는스타일") == ""


def test_default_is_maison():
    env = {k: v for k, v in os.environ.items() if k != "SCRIPT_STYLE"}
    with patch.dict(os.environ, env, clear=True):
        assert style_profiles.active_style() == "maison"


def test_wired_into_scene_first_prompt():
    """배선 테스트 — 함수만 검증하면 배선 한 줄 지워도 통과한다(이 트랙 실사고)."""
    seen = {}

    def fake_call(prompt, schema):
        seen["prompt"] = prompt
        return {"candidates": []}

    _scene_first_candidates("인벤토리", "제품설명", 30, call=fake_call)
    assert "스타일 예시" in seen["prompt"] and "소리 질렀어요" in seen["prompt"]

    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        _scene_first_candidates("인벤토리", "제품설명", 30, call=fake_call)
        assert "스타일 예시" not in seen["prompt"]  # off면 종전과 동일


def test_wired_into_single_source_prompt():
    """1소스 엔진 배선 — 3엔진 중 1개만 배선해 '적용 안 됨' 제보 났던 실사고(2026-08-05)."""
    from shopping_shorts.single_source import script_prompt
    order = [{"seg_id": "s0-1", "_dur": 3.0, "scene_desc": "장면", "text": "말", "is_key": True}]
    p = script_prompt(order, 10.0, "[훅블록]")
    assert "스타일 예시" in p and "소리 질렀어요" in p
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert "스타일 예시" not in script_prompt(order, 10.0, "[훅블록]")


def test_wired_into_script_generate_prompts():
    """도서관 3안(generate_variations)·믹스(script_generate) 엔진 배선."""
    from shopping_shorts import script_generate as sg
    assert "스타일 예시" in sg._style_extra()
    src = open(sg.__file__, encoding="utf-8").read()
    # 배선 줄 자체를 잠근다(함수만 검증하면 배선 삭제도 통과하는 함정 회피)
    assert src.count("+ _style_extra()") >= 2
