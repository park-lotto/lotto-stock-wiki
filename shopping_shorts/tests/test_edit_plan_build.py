import json
from shopping_shorts import edit_plan


def _scripts():
    return [
        {"video_id": "A", "full_text": "가방이 흥건",
         "segments": [{"seg_id": "A-0", "start": 0.0, "end": 2.0, "text": "훅", "scene_desc": "컵"}]},
        {"video_id": "B", "full_text": "안 흘러요",
         "segments": [{"seg_id": "B-0", "start": 0.0, "end": 3.0, "text": "반전", "scene_desc": "뒤집기"}]},
    ]


def _fake_gemini(monkeypatch, payload_text):
    class FakeResp:
        text = payload_text

    class FakeModels:
        def generate_content(self, **k): return FakeResp()

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr(edit_plan.comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(edit_plan.comment_gen, "_client_for_key", lambda key: FakeClient())
    monkeypatch.setattr(edit_plan, "SHORTS_GEMINI_KEYS", ["fake_key"])


def test_build_edit_plan_grounds_and_flags(monkeypatch):
    payload = json.dumps({"structure": "free", "affiliate_target": "소금", "beats": [
        {"role": "훅", "narration": "완전 새로운 훅", "target_seconds": 2,
         "primary": {"seg_id": "A-0", "start": 999}, "alternates": [{"seg_id": "B-0"}], "effect": "cut"},
        {"role": "반전", "narration": "안 흘러요", "target_seconds": 3,
         "primary": {"seg_id": "B-0"}, "alternates": []},
    ]})
    _fake_gemini(monkeypatch, payload)
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=5, structure="free",
                                     video_type="product_reveal")
    assert len(out["beats"]) == 2
    # 그라운딩: 모델의 start=999 무시하고 실제값
    assert out["beats"][0]["primary"]["start"] == 0.0
    assert out["beats"][0]["primary"]["end"] == 2.0
    # 표절: beat1 narration "안 흘러요"가 소스 full_text와 동일 → flag
    assert any(f["beat_idx"] == 1 for f in out["plagiarism_flags"])
    assert out["detected_type"] == "product_reveal"
    assert out["affiliate_target"] == "소금"


def test_build_edit_plan_structure_locked_to_input(monkeypatch):
    """모델이 raw structure에 지어낸 라벨(예: template_mode)을 줘도 입력 structure로 고정된다."""
    payload = json.dumps({"structure": "template_mode", "beats": [
        {"role": "훅", "narration": "훅 문장", "target_seconds": 2,
         "primary": {"seg_id": "A-0"}, "alternates": []},
    ]})
    _fake_gemini(monkeypatch, payload)
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=5, structure="template",
                                     video_type="recipe_secret")
    assert out["structure"] == "template"
    assert out["detected_type"] == "recipe_secret"


def test_build_edit_plan_exhausted_returns_empty(monkeypatch):
    monkeypatch.setattr(edit_plan.comment_gen, "_current_key_and_idx", lambda: (None, None))
    monkeypatch.setattr(edit_plan, "SHORTS_GEMINI_KEYS", ["fake_key"])
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=5, structure="template",
                                     video_type="product_reveal")
    assert out == {"structure": "template", "beats": [], "plagiarism_flags": [],
                    "detected_type": "product_reveal", "affiliate_target": ""}


def test_build_edit_plan_auto_detects_when_type_not_given(monkeypatch):
    """video_type을 안 주면 detect_video_type()을 호출해 결과에 반영한다."""
    payload = json.dumps({"structure": "template", "beats": [
        {"role": "훅", "narration": "훅 문장", "target_seconds": 2,
         "primary": {"seg_id": "A-0"}, "alternates": []},
    ]})
    _fake_gemini(monkeypatch, payload)
    monkeypatch.setattr(edit_plan, "detect_video_type", lambda scripts: "recipe_secret")
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=5, structure="template")
    assert out["detected_type"] == "recipe_secret"


def test_detect_video_type_returns_valid_key(monkeypatch):
    payload = json.dumps({"video_type": "recipe_secret"})
    _fake_gemini(monkeypatch, payload)
    result = edit_plan.detect_video_type(_scripts())
    assert result == "recipe_secret"


def test_detect_video_type_invalid_key_falls_back_to_default(monkeypatch):
    payload = json.dumps({"video_type": "존재하지않는유형"})
    _fake_gemini(monkeypatch, payload)
    result = edit_plan.detect_video_type(_scripts())
    assert result == edit_plan._DEFAULT_TYPE


def test_detect_video_type_key_exhausted_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(edit_plan.comment_gen, "_current_key_and_idx", lambda: (None, None))
    monkeypatch.setattr(edit_plan, "SHORTS_GEMINI_KEYS", ["fake_key"])
    result = edit_plan.detect_video_type(_scripts())
    assert result == edit_plan._DEFAULT_TYPE
