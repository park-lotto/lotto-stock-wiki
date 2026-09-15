import json
from pathlib import Path

from shopping_shorts import scene_style_lab


def test_compare_outputs_requires_zero_hook_captions_and_one_frame_tolerance():
    expected = {
        "hook_caption_count": 0,
        "body_first_start": 1.800,
        "clean_signature": "same-plan",
    }
    assert scene_style_lab.compare_contract(expected, {
        "hook_caption_count": 0,
        "body_first_start": 1.833,
        "clean_signature": "same-plan",
    })["ok"]
    assert not scene_style_lab.compare_contract(expected, {
        "hook_caption_count": 1,
        "body_first_start": 1.800,
        "clean_signature": "same-plan",
    })["ok"]
    assert not scene_style_lab.compare_contract(expected, {
        "hook_caption_count": 0,
        "body_first_start": 1.850,
        "clean_signature": "same-plan",
    })["ok"]
    assert not scene_style_lab.compare_contract(expected, {
        "hook_caption_count": 0,
        "body_first_start": 1.800,
        "clean_signature": "old-plan",
    })["ok"]


def test_contract_from_context_uses_visible_speech_only():
    context = {"scenes": [
        {"kind": "hook", "start": 0.0, "caption": "훅 음성", "caption_visible": False},
        {"kind": "body", "start": 1.8, "caption": "본문", "caption_visible": True},
    ]}
    contract = scene_style_lab.contract_from_context(context, "signature")
    assert contract == {
        "hook_caption_count": 0,
        "body_first_start": 1.8,
        "clean_signature": "signature",
    }


def test_fixture_has_explicit_hook_and_body_boundary():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "scene_style_lab_two_beats.json")
        .read_text(encoding="utf-8")
    )
    beats = fixture["edit_plan"]["beats"]
    assert beats[0]["role"] == "훅" and beats[0]["target_seconds"] == 1.8
    assert beats[1]["role"] == "본문"


def test_admin_lab_ui_exposes_four_output_comparison_and_actions():
    static = Path(__file__).parents[1] / "static"
    html = (static / "scene_style_lab.html").read_text(encoding="utf-8")
    script = (static / "scene-style-lab.js").read_text(encoding="utf-8")
    for label in ("미리보기", "MP4", "CapCut", "랜딩"):
        assert label in html
    for row in ("훅 자막", "본문 첫 시작", "청소본", "위치"):
        assert row in html
    assert "/render" in script
    assert "/capcut" in script
    assert "showDirectoryPicker" in script
    assert "/scene-style-lab/" in script
    assert "URLSearchParams" in script
    assert "render_state" in script
    assert "실파일 해시" in script
    assert "JSON 역검증" in script


def test_embedded_lab_does_not_restore_browser_local_branding():
    script = (Path(__file__).parents[2] / "out" / "precision20-ui.js").read_text(encoding="utf-8")
    assert "const labMode=query.get('lab')==='1'" in script
    assert "if(!qaMode&&!labMode)" in script
    assert "saved?.branding||{}).length?saved.branding:(labMode?{}:rememberedBranding())" in script
