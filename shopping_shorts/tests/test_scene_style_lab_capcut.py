import json
from copy import deepcopy
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


def test_capcut_overlay_verifier_accepts_30fps_microsecond_rounding():
    """1/30초 경계는 round(end)-round(start)라 프레임별 1μs 차이가 번갈아 난다."""
    kwargs = _draft_kwargs()
    expected = [
        {"_capcut_path": "C:/x/0.png", "start": 0.0, "end": 1 / 30},
        {"_capcut_path": "C:/x/1.png", "start": 1 / 30, "end": 2 / 30},
    ]
    kwargs["scene_overlay_layers"] = expected
    draft, _ = capcut_draft.build_draft(**kwargs)

    scene_style_lab.verify_capcut_overlay_draft(draft, expected)


def test_motion_layer_expands_to_30fps_frames_then_static_remainder(tmp_path):
    for name in (
        "scene-style-layer-0.png",
        "scene-style-motion-0-0000.png",
        "scene-style-motion-0-0001.png",
    ):
        (tmp_path / name).write_bytes(b"png")
    scene = {"start": 1.8, "end": 2.0, "caption_visible": True}
    layer = {
        "file": "scene-style-layer-0.png",
        "animation": {"pattern": "scene-style-motion-0-%04d.png", "count": 2},
        "camera": None,
    }

    specs = scene_style_lab.overlay_specs_for_scene(scene, layer, tmp_path)

    assert [(item["start"], item["end"]) for item in specs] == pytest.approx([
        (1.8, 1.8 + 1 / 30),
        (1.8 + 1 / 30, 1.8 + 2 / 30),
        (1.8 + 2 / 30, 2.0),
    ])
    assert [Path(item["path"]).name for item in specs] == [
        "scene-style-motion-0-0000.png",
        "scene-style-motion-0-0001.png",
        "scene-style-layer-0.png",
    ]


def test_capcut_copy_rejects_untransferred_camera_motion(tmp_path):
    (tmp_path / "scene-style-layer-0.png").write_bytes(b"png")
    with pytest.raises(scene_style_lab.LabPreconditionError, match="카메라 모션"):
        scene_style_lab.overlay_specs_for_scene(
            {"start": 0.0, "end": 1.0},
            {"file": "scene-style-layer-0.png", "camera": [{"scale": 1.1}]},
            tmp_path,
        )


def test_build_capcut_copy_uses_manifest_clean_source_and_updates_only_lab(tmp_path, monkeypatch):
    clean = tmp_path / "clean.mp4"
    tts0 = tmp_path / "b0.mp3"
    tts1 = tmp_path / "b1.mp3"
    for path in (clean, tts0, tts1):
        path.write_bytes(b"input")
    plan = deepcopy(PLAN)
    plan["beats"][0]["tts_path"] = str(tts0)
    plan["beats"][1]["tts_path"] = str(tts1)
    manifest = {
        "version": 1,
        "lab_id": "lab_000000000002",
        "source_job_id": "source",
        "source_plan_signature": scene_style_lab.clean_plan_signature(plan),
        "source_timing_signature": scene_style_lab.timing_signature(plan),
        "edit_plan": plan,
        "headcopy": {"text": "훅 제목"},
        "caption_style": {},
        "deco": {},
        "clean": {
            "kind": "sources",
            "paths": {"v0": str(clean)},
            "signature": scene_style_lab.clean_plan_signature(plan),
        },
        "scene_style": {
            "version": 1, "mode": "story", "presetId": "t11",
            "hookCaptionMode": "hidden",
        },
        "outputs": {},
    }
    source_job = {"job_id": "source", "edit_plan": deepcopy(plan)}
    source_before = deepcopy(source_job)
    target = scene_style_lab.lab_dir(tmp_path, manifest["lab_id"])
    target.mkdir(parents=True)
    scene_style_lab.write_manifest(target, manifest)
    monkeypatch.setattr(scene_style_lab.video_assemble, "_beat_timeline", lambda *_args: deepcopy(TIMELINE))

    def fake_layers(_timeline, _snapshot, output, **_kwargs):
        output = Path(output)
        result = []
        for index in range(2):
            name = f"scene-style-layer-{index}.png"
            (output / name).write_bytes(b"png")
            result.append({"file": name})
        return result

    captured = {}

    def fake_assemble(out_root, base_abs, **kwargs):
        captured.update(base_abs=base_abs, **kwargs)
        project = Path(out_root) / "LAB"
        project.mkdir(parents=True)
        draft, _ = capcut_draft.build_draft(
            plan=kwargs["plan"], timeline=kwargs["timeline"],
            source_video_paths=kwargs["source_video_paths"],
            tts_paths=kwargs["tts_paths"],
            asset_paths={str(clean): "C:/CapCut/LAB/clean.mp4",
                         str(tts0): "C:/CapCut/LAB/b0.mp3",
                         str(tts1): "C:/CapCut/LAB/b1.mp3"},
            project_name="LAB",
            scene_overlay_layers=[{**layer, "_capcut_path": f"C:/CapCut/LAB/{Path(layer['path']).name}"}
                                  for layer in kwargs["scene_overlay_layers"]],
        )
        (project / "draft_content.json").write_text(json.dumps(draft), encoding="utf-8")
        return project, "LAB", ["draft_content.json"]

    monkeypatch.setattr(scene_style, "render_layers", fake_layers)
    monkeypatch.setattr(capcut_draft, "assemble_draft_folder", fake_assemble)

    project = scene_style_lab.build_capcut_copy(
        manifest, source_job, tmp_path, "C:/CapCut Drafts"
    )

    assert project == target / "capcut" / "LAB"
    assert captured["source_video_paths"] == {"v0": str(clean)}
    assert captured["scene_overlay_layers"][0]["caption_visible"] is False
    assert captured["scene_overlay_layers"][1]["caption_visible"] is True
    assert source_job == source_before
    saved = scene_style_lab.read_manifest(tmp_path, manifest["lab_id"])
    assert saved["outputs"]["capcut_project"] == str(project)
    assert saved["contracts"]["capcut"]["hook_caption_count"] == 0
