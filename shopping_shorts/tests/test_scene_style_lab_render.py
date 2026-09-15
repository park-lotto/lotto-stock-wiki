from copy import deepcopy
from pathlib import Path
import wave

import pytest

from shopping_shorts import scene_style_lab


def _write_audio(path):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8_000)
        audio.writeframes(b"\0\0" * 8_000)


def _job(tts_path):
    return {
        "edit_plan": {
            "beats": [
                {
                    "beat_idx": 0,
                    "narration": "훅 대사",
                    "tts_path": str(tts_path),
                    "target_seconds": 1.0,
                    "primary": {"video_id": "s0", "start": 0.0, "end": 1.0},
                }
            ]
        },
        "headcopy": {"text": "훅 제목"},
        "caption_style": {"font_size": 72},
        "deco": {"watermark": {"text": "@source"}},
    }


def _manifest(job, clean):
    return {
        "version": 1,
        "lab_id": "lab_000000000001",
        "source_job_id": "j1",
        "source_plan_signature": scene_style_lab.clean_plan_signature(job["edit_plan"]),
        "edit_plan": deepcopy(job["edit_plan"]),
        "headcopy": deepcopy(job["headcopy"]),
        "caption_style": deepcopy(job["caption_style"]),
        "deco": deepcopy(job["deco"]),
        "clean": clean,
        "hook_caption_mode": "hidden",
        "scene_style": {
            "version": 1,
            "mode": "story",
            "presetId": "t11",
            "hookCaptionMode": "hidden",
        },
        "outputs": {},
    }


def test_render_uses_only_manifest_clean_sources_and_lab_output(tmp_path, monkeypatch):
    tts = tmp_path / "tts.mp3"
    clean = tmp_path / "clean.mp4"
    _write_audio(tts)
    clean.write_bytes(b"clean")
    job = _job(tts)
    manifest = _manifest(
        job,
        {"kind": "sources", "paths": {"s0": str(clean)},
         "signature": scene_style_lab.clean_plan_signature(job["edit_plan"])},
    )
    target = scene_style_lab.lab_dir(tmp_path, manifest["lab_id"])
    target.mkdir(parents=True)
    scene_style_lab.write_manifest(target, manifest)
    calls = []

    def fake_assemble(plan, tts_paths, sources, out_path, **kwargs):
        calls.append((plan, tts_paths, sources, out_path, kwargs))
        Path(out_path).write_bytes(b"rendered")
        return out_path

    monkeypatch.setattr(scene_style_lab.video_assemble, "assemble", fake_assemble)

    output = scene_style_lab.render_copy(manifest, job, tmp_path)

    assert calls[0][2] == {"s0": str(clean)}
    assert calls[0][3] == str(target / "lab-final.mp4")
    assert calls[0][4]["deco"]["scene_style"]["hookCaptionMode"] == "hidden"
    assert output == target / "lab-final.mp4"
    saved = scene_style_lab.read_manifest(tmp_path, manifest["lab_id"])
    assert saved["outputs"]["mp4"] == str(output)
    assert saved["contracts"]["mp4"]["hook_caption_count"] == 0
    assert saved["contracts"]["landing"] == saved["contracts"]["mp4"]


def test_render_final_clean_uses_live_split_and_plan_adapters(tmp_path, monkeypatch):
    tts = tmp_path / "tts.mp3"
    clean_final = tmp_path / "final-clean.mp4"
    clip = tmp_path / "lab0.mp4"
    _write_audio(tts)
    for path in (clean_final, clip):
        path.write_bytes(b"data")
    job = _job(tts)
    manifest = _manifest(
        job,
        {"kind": "final", "path": str(clean_final),
         "signature": scene_style_lab.clean_plan_signature(job["edit_plan"])},
    )
    target = scene_style_lab.lab_dir(tmp_path, manifest["lab_id"])
    target.mkdir(parents=True)
    scene_style_lab.write_manifest(target, manifest)
    split_calls = []
    plan_calls = []

    monkeypatch.setattr(
        scene_style_lab.video_assemble,
        "_beat_timeline",
        lambda plan, tts_paths: [{"beat_idx": 0, "t0": 0.0, "dur": 1.0}],
    )
    monkeypatch.setattr(
        scene_style_lab.mix_pipeline,
        "split_final_into_beat_clips",
        lambda path, timeline, work, prefix="cc": split_calls.append((path, timeline, work, prefix)) or {"lab0": str(clip)},
    )
    monkeypatch.setattr(
        scene_style_lab.mix_pipeline,
        "plan_using_beat_clips",
        lambda plan, clips, timeline, prefix="cc": plan_calls.append((plan, clips, timeline, prefix)) or {"beats": plan["beats"]},
    )
    monkeypatch.setattr(
        scene_style_lab.video_assemble,
        "assemble",
        lambda plan, tts_paths, sources, out_path, **kwargs: Path(out_path).write_bytes(b"rendered"),
    )

    scene_style_lab.render_copy(manifest, job, tmp_path)

    assert split_calls[0][0] == str(clean_final)
    assert split_calls[0][3] == "lab"
    assert plan_calls[0][1] == {"lab0": str(clip)}
    assert plan_calls[0][3] == "lab"


def test_render_rejects_missing_or_replaced_clean_file(tmp_path):
    tts = tmp_path / "tts.mp3"
    _write_audio(tts)
    job = _job(tts)
    manifest = _manifest(
        job,
        {"kind": "final", "path": str(tmp_path / "missing.mp4"),
         "signature": scene_style_lab.clean_plan_signature(job["edit_plan"])},
    )

    with pytest.raises(scene_style_lab.LabPreconditionError, match="청소본"):
        scene_style_lab.render_copy(manifest, job, tmp_path)


def test_render_rejects_source_job_changed_after_copy(tmp_path):
    tts = tmp_path / "tts.mp3"
    clean = tmp_path / "clean.mp4"
    _write_audio(tts)
    clean.write_bytes(b"clean")
    job = _job(tts)
    manifest = _manifest(
        job,
        {"kind": "sources", "paths": {"s0": str(clean)},
         "signature": scene_style_lab.clean_plan_signature(job["edit_plan"])},
    )
    job["edit_plan"]["beats"][0]["primary"]["start"] = 0.25

    with pytest.raises(scene_style_lab.LabPreconditionError, match="바뀌었습니다"):
        scene_style_lab.render_copy(manifest, job, tmp_path)


def test_clean_preview_for_sources_never_uses_original_video(tmp_path, monkeypatch):
    tts = tmp_path / "tts.mp3"
    clean = tmp_path / "clean.mp4"
    _write_audio(tts)
    clean.write_bytes(b"clean")
    job = _job(tts)
    manifest = _manifest(
        job,
        {"kind": "sources", "paths": {"s0": str(clean)},
         "signature": scene_style_lab.clean_plan_signature(job["edit_plan"])},
    )
    calls = []

    def fake_assemble(plan, tts_paths, sources, out_path, **kwargs):
        calls.append((sources, out_path, kwargs))
        Path(out_path).write_bytes(b"preview")

    monkeypatch.setattr(scene_style_lab.video_assemble, "assemble", fake_assemble)

    preview = scene_style_lab.clean_preview_for(manifest, job, tmp_path)

    assert calls[0][0] == {"s0": str(clean)}
    assert calls[0][2]["burn_captions"] is False
    assert preview.name == "lab-clean-preview.mp4"


def test_clean_preview_for_final_returns_exact_clean_file(tmp_path, monkeypatch):
    tts = tmp_path / "tts.mp3"
    clean = tmp_path / "final-clean.mp4"
    _write_audio(tts)
    clean.write_bytes(b"clean")
    job = _job(tts)
    manifest = _manifest(
        job,
        {"kind": "final", "path": str(clean),
         "signature": scene_style_lab.clean_plan_signature(job["edit_plan"])},
    )
    monkeypatch.setattr(
        scene_style_lab.video_assemble,
        "assemble",
        lambda *_args, **_kwargs: pytest.fail("완성본 청소본을 다시 조립하면 안 됨"),
    )

    assert scene_style_lab.clean_preview_for(manifest, job, tmp_path) == clean


def test_frame_for_scene_extracts_from_clean_preview_at_scene_midpoint(tmp_path, monkeypatch):
    tts = tmp_path / "tts.mp3"
    clean = tmp_path / "clean.mp4"
    _write_audio(tts)
    clean.write_bytes(b"clean")
    job = _job(tts)
    manifest = _manifest(
        job,
        {"kind": "final", "path": str(clean),
         "signature": scene_style_lab.clean_plan_signature(job["edit_plan"])},
    )
    calls = []

    monkeypatch.setattr(
        scene_style_lab.video_assemble,
        "_beat_timeline",
        lambda plan, tts_paths: [
            {"beat_idx": 0, "t0": 0.0, "dur": 1.0, "narration": "훅 대사"}
        ],
    )

    def fake_extract(source, output_dir, at, filename):
        calls.append((source, output_dir, at, filename))
        output = Path(output_dir) / filename
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"jpg")
        return output

    monkeypatch.setattr(scene_style_lab.frame_extract, "extract_frame_at", fake_extract)

    frame = scene_style_lab.frame_for_scene(manifest, job, tmp_path, 0)

    assert calls[0][0] == str(clean)
    assert calls[0][2] == pytest.approx(0.5)
    assert frame.name == "scene-0000.jpg"
