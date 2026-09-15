import json
from pathlib import Path

import pytest

from shopping_shorts import capcut_draft, scene_style, scene_style_lab


PLAN = {"beats": [
    {"beat_idx": 0, "role": "훅", "narration": "훅 음성",
     "primary": {"video_id": "v0", "start": 0.0, "end": 1.8}},
    {"beat_idx": 1, "role": "본문", "narration": "본문 음성",
     "primary": {"video_id": "v0", "start": 1.8, "end": 3.0}},
]}
TIMELINE = [
    {"beat_idx": 0, "role": "훅", "narration": "훅 음성", "t0": 0.0, "dur": 1.8},
    {"beat_idx": 1, "role": "본문", "narration": "본문 음성", "t0": 1.8, "dur": 1.2},
]


def _draft_kwargs():
    return {
        "plan": PLAN,
        "timeline": TIMELINE,
        "source_video_paths": {"v0": "C:/real/clean.mp4"},
        "tts_paths": {0: "C:/real/beat0.mp3", 1: "C:/real/beat1.mp3"},
        "asset_paths": {
            "C:/real/clean.mp4": "C:/CapCut/LAB/clean.mp4",
            "C:/real/beat0.mp3": "C:/CapCut/LAB/beat0.mp3",
            "C:/real/beat1.mp3": "C:/CapCut/LAB/beat1.mp3",
        },
        "project_name": "LAB",
    }


def test_render_layers_uses_validated_snapshot_and_real_caption_context(tmp_path, monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        request = json.loads((tmp_path / "scene-style-request.json").read_text(encoding="utf-8"))
        captured["request"] = request
        (tmp_path / "scene-style-layers.json").write_text(
            json.dumps([{"file": "scene-style-layer-0.png"}]), encoding="utf-8"
        )
        return type("Run", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(scene_style.subprocess, "run", fake_run)
    layers = scene_style.render_layers(
        [TIMELINE[0]],
        {"version": 1, "mode": "story", "presetId": "t11", "hookCaptionMode": "hidden"},
        tmp_path,
        headcopy={"text": "두 줄\n훅 제목"},
    )

    assert layers == [{"file": "scene-style-layer-0.png"}]
    assert captured["request"]["context"]["scenes"][0]["caption"] == "훅 음성"
    assert captured["request"]["context"]["scenes"][0]["caption_visible"] is False
    assert captured["request"]["output"] == str(tmp_path.resolve())


def test_scene_overlay_replaces_native_speech_captions_in_capcut():
    kwargs = _draft_kwargs()
    kwargs["scene_overlay_layers"] = [
        {"_capcut_path": "C:/CapCut/LAB/scene-0.png", "start": 0.0, "end": 1.8},
        {"_capcut_path": "C:/CapCut/LAB/scene-1.png", "start": 1.8, "end": 3.0},
    ]
    draft, _ = capcut_draft.build_draft(**kwargs)

    overlay = next(track for track in draft["tracks"] if track["name"] == "scene-style-overlay")
    assert [segment["target_timerange"] for segment in overlay["segments"]] == [
        {"start": 0, "duration": 1_800_000},
        {"start": 1_800_000, "duration": 1_200_000},
    ]
    assert not any(track["type"] == "text" for track in draft["tracks"])
    overlay_ids = {segment["material_id"] for segment in overlay["segments"]}
    overlay_materials = [m for m in draft["materials"]["videos"] if m["id"] in overlay_ids]
    assert [m["path"] for m in overlay_materials] == [
        "C:/CapCut/LAB/scene-0.png", "C:/CapCut/LAB/scene-1.png"
    ]


def test_build_draft_accepts_real_layer_paths_through_asset_mapping():
    kwargs = _draft_kwargs()
    kwargs["asset_paths"]["C:/real/layer.png"] = "C:/CapCut/LAB/layer.png"
    kwargs["scene_overlay_layers"] = [
        {"path": "C:/real/layer.png", "t0": 0.0, "dur": 1.8,
         "caption_visible": False},
    ]

    draft, assets = capcut_draft.build_draft(**kwargs)

    overlay = next(track for track in draft["tracks"] if track["name"] == "scene-style-overlay")
    assert overlay["segments"][0]["target_timerange"] == {"start": 0, "duration": 1_800_000}
    assert ("C:/real/layer.png", "C:/CapCut/LAB/layer.png") in assets


def test_capcut_without_scene_overlay_keeps_existing_native_captions():
    draft, _ = capcut_draft.build_draft(**_draft_kwargs())
    assert any(track["type"] == "text" and track["segments"] for track in draft["tracks"])
    assert not any(track["name"] == "scene-style-overlay" for track in draft["tracks"])


def test_assemble_draft_folder_copies_scene_overlay_assets(tmp_path, monkeypatch):
    clean = tmp_path / "clean.mp4"
    beat0 = tmp_path / "beat0.mp3"
    beat1 = tmp_path / "beat1.mp3"
    layer0 = tmp_path / "layer0.png"
    layer1 = tmp_path / "layer1.png"
    for path in (clean, beat0, beat1, layer0, layer1):
        path.write_bytes(b"test")
    monkeypatch.setattr(capcut_draft, "_cut", lambda *_args, **_kwargs: False)

    project, _, files = capcut_draft.assemble_draft_folder(
        tmp_path / "drafts",
        "C:/CapCut Drafts",
        plan=PLAN,
        timeline=TIMELINE,
        source_video_paths={"v0": str(clean)},
        tts_paths={0: str(beat0), 1: str(beat1)},
        project_name="LAB copy",
        probe=lambda _path: 3.0,
        scene_overlay_layers=[
            {"path": str(layer0), "start": 0.0, "end": 1.8},
            {"path": str(layer1), "start": 1.8, "end": 3.0},
        ],
    )

    assert {"scene-style-0000.png", "scene-style-0001.png"} <= set(files)
    draft = json.loads((project / "draft_content.json").read_text(encoding="utf-8"))
    overlay = next(track for track in draft["tracks"] if track["name"] == "scene-style-overlay")
    paths = {m["id"]: m["path"] for m in draft["materials"]["videos"]}
    assert [paths[s["material_id"]] for s in overlay["segments"]] == [
        "C:/CapCut Drafts/LAB copy/scene-style-0000.png",
        "C:/CapCut Drafts/LAB copy/scene-style-0001.png",
    ]


def test_capcut_overlay_verifier_rejects_timing_mismatch():
    kwargs = _draft_kwargs()
    expected = [{"start": 0.0, "end": 1.8}, {"start": 1.8, "end": 3.0}]
    kwargs["scene_overlay_layers"] = [
        {"_capcut_path": "C:/x/0.png", **expected[0]},
        {"_capcut_path": "C:/x/1.png", **expected[1]},
    ]
    draft, _ = capcut_draft.build_draft(**kwargs)
    scene_style_lab.verify_capcut_overlay_draft(draft, expected)
    draft["tracks"][-1]["segments"][1]["target_timerange"]["start"] += 1
    with pytest.raises(scene_style_lab.LabPreconditionError, match="타이밍"):
        scene_style_lab.verify_capcut_overlay_draft(draft, expected)
