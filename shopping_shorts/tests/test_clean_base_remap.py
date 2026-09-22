# -*- coding: utf-8 -*-
"""청소본 정본(clean base) — 재료가 그대로면 청소본 좌표로, 바뀌면 uncovered (2026-09-22)."""
import json
import pytest

from shopping_shorts import clean_base as cb


def _plan():
    return {"beats": [
        {"beat_idx": 0, "target_seconds": 2.0, "narration": "첫 줄",
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 10.0, "end": 14.0}, "alternates": []},
        {"beat_idx": 1, "target_seconds": 3.0, "narration": "둘째 줄",
         "primary": {"video_id": "s1", "seg_id": "s1-0", "start": 5.0, "end": 9.0},
         "alternates": [{"video_id": "s2", "seg_id": "s2-0", "start": 1.0, "end": 3.0}]},
    ]}


def _cuts():
    # 청소 시점 컷 지도: beat0 = clean 0.0~2.0 (s0 10.0부터), beat1 = clean 2.0~4.0(s1) + 4.0~5.0(s2)
    return [
        {"video_id": "s0", "beat_idx": 0, "src": 10.0, "fin": 0.0, "dur": 2.0},
        {"video_id": "s1", "beat_idx": 1, "src": 5.0, "fin": 2.0, "dur": 2.0},
        {"video_id": "s2", "beat_idx": 1, "src": 1.0, "fin": 4.0, "dur": 1.0},
    ]


@pytest.fixture
def base(tmp_path):
    (tmp_path / "final_clean_abc.mp4").write_bytes(b"x" * 2048)
    return cb.save_base(tmp_path, sig="abc", path=str(tmp_path / "final_clean_abc.mp4"),
                        plan=_plan(), cuts=_cuts())


def test_save_then_load_roundtrip(tmp_path, base):
    got = cb.load_base(tmp_path)
    assert got["sig"] == "abc" and got["cuts"] == _cuts() and got["extras"] == {}
    assert json.loads((tmp_path / cb.BASE_FILE).read_text(encoding="utf-8"))["sig"] == "abc"


def test_load_none_when_file_missing(tmp_path):
    assert cb.load_base(tmp_path) is None


def test_load_none_when_clean_mp4_missing(tmp_path, base):
    (tmp_path / "final_clean_abc.mp4").unlink()
    assert cb.load_base(tmp_path) is None


def test_coverage_same_materials_is_covered(base):
    assert cb.coverage(_plan(), base) == {0: "covered", 1: "covered"}


def test_coverage_caption_lines_and_zoom_do_not_matter(base):
    p = _plan()
    p["beats"][0]["caption_lines"] = ["첫", "줄"]
    p["beats"][1]["scene_zoom"] = 1.2
    p["beats"][1]["target_seconds"] = 3.4
    assert cb.coverage(p, base) == {0: "covered", 1: "covered"}


def test_coverage_changed_material_and_new_beat(base):
    p = _plan()
    p["beats"][0]["scene_override"] = [{"video_id": "s3", "seg_id": "s3-0", "start": 0.0, "end": 2.0}]
    p["beats"].append({"beat_idx": 2, "target_seconds": 1.0,
                       "primary": {"video_id": "s0", "seg_id": "s0-1", "start": 20.0, "end": 22.0}, "alternates": []})
    assert cb.coverage(p, base) == {0: "changed", 1: "covered", 2: "new"}


def test_remap_replaces_materials_with_clean_coords(base):
    p = _plan()
    p["beats"][0]["caption_lines"] = ["첫", "줄"]          # 자막 편집은 살아남는다
    plan2, uncovered, extend = cb.remap_plan(p, base)
    assert uncovered == [] and extend == []
    b0, b1 = plan2["beats"]
    assert b0["scene_override"] == [{"video_id": "clean", "seg_id": "clean-0", "start": 0.0, "end": 2.0}]
    assert b1["scene_override"] == [{"video_id": "clean", "seg_id": "clean-1", "start": 2.0, "end": 4.0},
                                    {"video_id": "clean", "seg_id": "clean-2", "start": 4.0, "end": 5.0}]
    assert b0["caption_lines"] == ["첫", "줄"]
    assert plan2["clean_base"] is True
    assert p["beats"][0].get("scene_override") is None       # 원본은 안 건드린다


def test_remap_keeps_original_materials_for_uncovered(base):
    p = _plan()
    p["beats"][0]["scene_override"] = [{"video_id": "s3", "seg_id": "s3-0", "start": 0.0, "end": 2.0}]
    plan2, uncovered, _ = cb.remap_plan(p, base)
    assert uncovered == [0]
    assert plan2["beats"][0]["scene_override"][0]["video_id"] == "s3"


def test_remap_extend_request_when_much_longer(base):
    p = _plan()
    p["beats"][0]["target_seconds"] = 2.0 * 1.5     # 청소본에 2.0초뿐 → 50% 모자람 > EXTEND_MIN
    plan2, uncovered, extend = cb.remap_plan(p, base, tts_durs={0: 3.0})
    assert uncovered == []
    assert extend == [{"beat_idx": 0, "video_id": "s0", "start": 12.0, "end": 13.2, "need": 1.0}]


def test_remap_no_extend_when_slightly_longer(base):
    p = _plan()
    plan2, _, extend = cb.remap_plan(p, base, tts_durs={0: 2.4})     # 20% → 느리게+정지로 채운다
    assert extend == []


def test_extras_cover_changed_beat(tmp_path, base):
    p = _plan()
    p["beats"][0]["scene_override"] = [{"video_id": "s3", "seg_id": "s3-0", "start": 0.0, "end": 2.0}]
    (tmp_path / "cb0_0.mp4").write_bytes(b"x" * 2048)
    cb.add_extra(tmp_path, base, vid="cb0_0", path=str(tmp_path / "cb0_0.mp4"),
                 beat_idx=0, material_key=cb.beat_material_key(p["beats"][0]), seconds=2.0)
    base2 = cb.load_base(tmp_path)
    assert cb.coverage(p, base2) == {0: "covered", 1: "covered"}
    plan2, uncovered, _ = cb.remap_plan(p, base2)
    assert uncovered == []
    assert plan2["beats"][0]["scene_override"] == [{"video_id": "cb0_0", "seg_id": "cb0_0", "start": 0.0, "end": 2.0}]
    assert cb.source_paths(base2) == {"clean": base2["path"], "cb0_0": str(tmp_path / "cb0_0.mp4")}


def test_time_in_clean(base):
    assert cb.time_in_clean(base, 1, pos=0.0) == 2.0
    assert cb.time_in_clean(base, 1, pos=0.5) == pytest.approx(3.5)
    assert cb.time_in_clean(base, 7) is None
