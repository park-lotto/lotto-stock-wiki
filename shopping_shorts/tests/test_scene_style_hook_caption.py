from pathlib import Path

import pytest

from shopping_shorts import scene_style


def test_context_hides_every_hook_caption_without_changing_text_or_time(monkeypatch):
    from shopping_shorts import video_assemble

    def fake_schedule(beat):
        if beat["beat_idx"] == 0:
            return [
                ("훅 첫줄", 0.2, 0.9),
                ("훅 둘째줄", 0.9, 1.8),
            ]
        return [("본문 대사", 1.8, 3.8)]

    monkeypatch.setattr(video_assemble, "caption_schedule", fake_schedule)
    timeline = [
        {"beat_idx": 0, "t0": 0.0, "dur": 1.8, "narration": "훅 대사"},
        {"beat_idx": 1, "t0": 1.8, "dur": 2.0, "narration": "본문 대사"},
    ]

    context = scene_style.context_for(
        timeline,
        snapshot={"hookCaptionMode": "hidden"},
    )

    hook_scenes = [scene for scene in context["scenes"] if scene["kind"] == "hook"]
    body_scene = next(scene for scene in context["scenes"] if scene["kind"] == "body")
    # 2026-09-21: 자막 리드 자투리는 이웃 구절이 삼킨다(빈 장면을 세우지 않는다).
    #   이 테스트가 지키는 본질은 **훅 자막 숨김과 시간 보존**이고 그건 아래에서 그대로 검사한다.
    assert [scene["caption"] for scene in hook_scenes] == ["훅 첫줄", "훅 둘째줄"]
    assert all(scene["caption_visible"] is False for scene in hook_scenes)
    assert body_scene["caption_visible"] is True
    assert (body_scene["start"], body_scene["end"]) == (1.8, 3.8)


def test_context_keeps_legacy_caption_visibility_when_policy_is_absent(monkeypatch):
    from shopping_shorts import video_assemble

    monkeypatch.setattr(
        video_assemble,
        "caption_schedule",
        lambda beat: [(beat["narration"], beat["t0"], beat["t0"] + beat["dur"])],
    )
    context = scene_style.context_for(
        [{"beat_idx": 0, "t0": 0.0, "dur": 1.0, "narration": "기존 훅"}],
        snapshot={},
    )

    assert context["scenes"][0]["caption_visible"] is True


def test_snapshot_validation_preserves_hook_caption_mode():
    saved = scene_style.validate_snapshot(
        {"mode": "story", "presetId": "t11", "hookCaptionMode": "hidden"}
    )

    assert saved["hookCaptionMode"] == "hidden"


def test_snapshot_validation_rejects_unknown_hook_caption_mode():
    with pytest.raises(ValueError, match="훅 말자막"):
        scene_style.validate_snapshot(
            {"mode": "story", "presetId": "t11", "hookCaptionMode": "erase-text"}
        )


def test_ui_uses_explicit_caption_visibility_and_preserves_policy():
    root = Path(__file__).resolve().parents[2]
    js = (root / "out" / "precision20-ui.js").read_text(encoding="utf-8")

    assert "caption_visible!==false" in js
    assert "hookCaptionMode" in js
    assert "if(!captionVisible())return" in js
