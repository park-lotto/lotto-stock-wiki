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
    payload = json.dumps({"structure": "free", "beats": [
        {"role": "훅", "narration": "완전 새로운 훅", "target_seconds": 2,
         "primary": {"seg_id": "A-0", "start": 999}, "alternates": [{"seg_id": "B-0"}], "effect": "cut"},
        {"role": "반전", "narration": "안 흘러요", "target_seconds": 3,
         "primary": {"seg_id": "B-0"}, "alternates": []},
    ]})
    _fake_gemini(monkeypatch, payload)
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=5, structure="free")
    assert len(out["beats"]) == 2
    # 그라운딩: 모델의 start=999 무시하고 실제값
    assert out["beats"][0]["primary"]["start"] == 0.0
    assert out["beats"][0]["primary"]["end"] == 2.0
    # 표절: beat1 narration "안 흘러요"가 소스 full_text와 동일 → flag
    assert any(f["beat_idx"] == 1 for f in out["plagiarism_flags"])


def test_build_edit_plan_exhausted_returns_empty(monkeypatch):
    monkeypatch.setattr(edit_plan.comment_gen, "_current_key_and_idx", lambda: (None, None))
    monkeypatch.setattr(edit_plan, "SHORTS_GEMINI_KEYS", ["fake_key"])
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=5, structure="template")
    assert out == {"structure": "template", "beats": [], "plagiarism_flags": []}
