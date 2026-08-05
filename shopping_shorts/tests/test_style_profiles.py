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


def test_single_source_line_count_longer_sentences_when_style_on():
    """스타일 ON이면 문장 수가 줄어 긴 호흡이 된다 (30초: 8~9문장 → 6문장)."""
    from shopping_shorts.single_source import line_count
    assert line_count(30.0, 13) == 6
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert line_count(30.0, 13) == 9  # 종전과 동일


def _mk_beats():
    return [{"n": 1, "covers": [1], "narration": "다이소에서 역대급 스팀기를 발견했어요."},
            {"n": 2, "covers": [2, 3], "narration": "물만으로 살균까지 되니 정말 편해요."},
            {"n": 3, "covers": [4], "narration": "댓글에 '정보' 남겨주시면 링크 드릴게요."}]


def test_apply_restyle_swaps_narration_keeps_covers():
    from shopping_shorts.single_source import apply_restyle
    def fake_call(prompt, schema):
        assert "스타일 예시" in prompt      # few-shot이 실려 간다
        return {"beats": [{"n": 1, "narration": "와, 저 이거 보고 소리 질렀거든요."},
                          {"n": 2, "narration": "물만으로 살균까지 되는 게 편하더라고요."},
                          {"n": 3, "narration": "댓글에 '정보' 남겨주시면 링크 드릴게요."}]}
    out = apply_restyle(_mk_beats(), fake_call)
    assert out[0]["narration"].startswith("와,") and out[0]["covers"] == [1]
    assert out[1]["covers"] == [2, 3]      # 컷 매핑 보존


def test_apply_restyle_falls_back_on_bad_response():
    from shopping_shorts.single_source import apply_restyle
    src = _mk_beats()
    assert apply_restyle(src, lambda *a: None) == src              # 실패 → 원본
    assert apply_restyle(src, lambda *a: {"beats": [{"n": 1, "narration": "x"}]}) == src  # 개수 불일치
    with patch.dict(os.environ, {"SCRIPT_STYLE": "off"}):
        assert apply_restyle(src, lambda *a: (_ for _ in ()).throw(AssertionError)) == src  # off=무호출


def test_apply_restyle_retries_on_cliche():
    from shopping_shorts.single_source import apply_restyle
    calls = {"n": 0}
    def fake_call(prompt, schema):
        calls["n"] += 1
        word = "꿀템이에요" if calls["n"] == 1 else "괜찮더라고요"
        return {"beats": [{"n": i + 1, "narration": f"이 제품 써봤는데 진짜 {word}."}
                          for i in range(3)]}
    out = apply_restyle(_mk_beats(), fake_call)
    assert calls["n"] == 2 and "꿀템" not in out[0]["narration"]


def test_wired_into_script_generate_prompts():
    """도서관 3안(generate_variations)·믹스(script_generate) 엔진 배선."""
    from shopping_shorts import script_generate as sg
    assert "스타일 예시" in sg._style_extra()
    src = open(sg.__file__, encoding="utf-8").read()
    # 배선 줄 자체를 잠근다(함수만 검증하면 배선 삭제도 통과하는 함정 회피)
    assert src.count("+ _style_extra()") >= 2
