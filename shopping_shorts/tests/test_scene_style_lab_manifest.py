from copy import deepcopy
from pathlib import Path

import pytest


def test_create_lab_copy_requires_fresh_clean_and_keeps_source_unchanged(tmp_path, monkeypatch):
    from shopping_shorts import scene_style_lab as lab

    job = {
        "edit_plan": {
            "beats": [
                {"beat_idx": 0, "narration": "훅", "tts_path": "a.mp3"},
            ]
        }
    }
    before = deepcopy(job)
    monkeypatch.setattr(lab, "resolve_clean_contract", lambda *_args: None)

    with pytest.raises(lab.LabPreconditionError, match="청소본"):
        lab.create_copy("job1", job, tmp_path)

    assert job == before


def test_create_lab_copy_writes_isolated_manifest(tmp_path, monkeypatch):
    from shopping_shorts import scene_style_lab as lab

    clean_path = tmp_path / "clean.mp4"
    clean_path.write_bytes(b"clean")
    job = {
        "edit_plan": {
            "beats": [
                {"beat_idx": 0, "narration": "훅", "tts_path": "a.mp3"},
            ]
        },
        "headcopy": {"text": "큰 훅 제목"},
        "caption_style": {"font_size": 72},
        "deco": {"watermark": {"text": "@lab"}},
    }
    monkeypatch.setattr(
        lab,
        "resolve_clean_contract",
        lambda *_args: {"kind": "final", "path": str(clean_path), "signature": "clean-sig"},
    )

    manifest = lab.create_copy("job1", job, tmp_path)

    assert manifest["lab_id"].startswith("lab_")
    assert manifest["source_job_id"] == "job1"
    assert manifest["clean"]["path"] == str(clean_path)
    assert manifest["hook_caption_mode"] == "hidden"
    assert manifest["scene_style"]["hookCaptionMode"] == "hidden"
    assert manifest["scene_style"]["mode"] == "story"
    assert manifest["edit_plan"] is not job["edit_plan"]
    assert lab.read_manifest(tmp_path, manifest["lab_id"]) == manifest


def test_assert_fresh_rejects_changed_clean_plan_signature():
    from shopping_shorts import scene_style_lab as lab

    source = {"edit_plan": {"beats": [{"beat_idx": 0, "narration": "바뀌 문장"}]}}
    manifest = {
        "source_plan_signature": "old",
        "edit_plan": {"beats": []},
    }

    with pytest.raises(lab.LabPreconditionError, match="바뀌었습니다"):
        lab.assert_fresh(manifest, source)


@pytest.mark.parametrize("bad", ["../x", "lab_x", "", "lab_1234/xx"])
def test_lab_dir_rejects_bad_id(tmp_path, bad):
    from shopping_shorts import scene_style_lab as lab

    with pytest.raises(ValueError):
        lab.lab_dir(tmp_path, bad)


def test_resolve_clean_contract_never_falls_back_to_preview_or_video(tmp_path):
    from shopping_shorts import scene_style_lab as lab

    preview = tmp_path / "preview.mp4"
    video = tmp_path / "video.mp4"
    preview.write_bytes(b"preview")
    video.write_bytes(b"video")
    job = {
        "edit_plan": {"beats": [{"beat_idx": 0}]},
        "preview_path": str(preview),
        "video_path": str(video),
    }

    assert lab.resolve_clean_contract(job, tmp_path) is None


def test_resolve_clean_contract_accepts_only_existing_source_files(tmp_path):
    from shopping_shorts import scene_style_lab as lab

    clean = tmp_path / "source-clean.mp4"
    clean.write_bytes(b"clean")
    job = {
        "edit_plan": {"beats": [{"beat_idx": 0}]},
        "clean_sources": {"s0": str(clean), "s1": str(tmp_path / "missing.mp4")},
    }

    assert lab.resolve_clean_contract(job, tmp_path) is None

    job["clean_sources"].pop("s1")
    contract = lab.resolve_clean_contract(job, tmp_path)
    assert contract == {
        "kind": "sources",
        "paths": {"s0": str(clean)},
        "signature": lab.clean_plan_signature(job["edit_plan"]),
    }
