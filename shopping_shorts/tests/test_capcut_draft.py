"""CapCut draft 생성기 구조 검증 (설계 부록A). 실제 열림 여부는 캡컷 육안(자동 불가)."""
from shopping_shorts import capcut_draft as cd


_PLAN = {"beats": [
    {"beat_idx": 0, "role": "훅", "narration": "첫 장면",
     "primary": {"video_id": "s0", "start": 0.0, "end": 2.0}},
    {"beat_idx": 1, "role": "본문", "narration": "둘째 장면",
     "primary": {"video_id": "s0", "start": 2.0, "end": 3.5}}]}
_TIMELINE = [
    {"beat_idx": 0, "t0": 0.0, "dur": 2.0, "narration": "첫 장면", "role": "훅"},
    {"beat_idx": 1, "t0": 2.0, "dur": 1.5, "narration": "둘째 장면", "role": "본문"}]
_SRC = {"s0": r"C:\real\src.mp4"}
_TTS = {0: r"C:\real\b0.mp3", 1: r"C:\real\b1.mp3"}
_ASSET = {r"C:\real\src.mp4": r"C:\cap\p\src.mp4",
          r"C:\real\b0.mp3": r"C:\cap\p\b0.mp3", r"C:\real\b1.mp3": r"C:\cap\p\b1.mp3"}


def _build():
    return cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                          tts_paths=_TTS, asset_paths=_ASSET, project_name="테스트")


def test_us_conversion():
    assert cd._us(1) == 1_000_000
    assert cd._us(2.5) == 2_500_000
    assert cd._us(-1) == 0


def test_three_tracks_with_segments():
    draft, _ = _build()
    types = {t["type"]: len(t["segments"]) for t in draft["tracks"]}
    assert types == {"video": 2, "audio": 2, "text": 2}


def test_timeline_microseconds():
    draft, _ = _build()
    txt = next(t for t in draft["tracks"] if t["type"] == "text")
    # 둘째 자막은 t0=2.0s → 2_000_000μs 에서 시작, 길이 1.5s
    seg1 = txt["segments"][1]
    assert seg1["target_timerange"] == {"start": 2_000_000, "duration": 1_500_000}
    assert seg1["source_timerange"] is None   # 텍스트는 source 없음
    assert draft["duration"] == 3_500_000     # 전체 = 마지막 끝


def test_extra_material_refs_resolve():
    """세그먼트가 참조하는 동반 material이 실제로 materials에 있어야 캡컷이 연다."""
    draft, _ = _build()
    ids = set()
    for arr in draft["materials"].values():
        for m in arr:
            ids.add(m["id"])
    for tr in draft["tracks"]:
        for seg in tr["segments"]:
            assert seg["material_id"] in ids, f"material_id 미해결: {seg['material_id']}"
            for ref in seg["extra_material_refs"]:
                assert ref in ids, f"extra_material_ref 미해결: {ref}"


def test_audio_has_five_companions_text_one():
    draft, _ = _build()
    aud = next(t for t in draft["tracks"] if t["type"] == "audio")
    txt = next(t for t in draft["tracks"] if t["type"] == "text")
    assert len(aud["segments"][0]["extra_material_refs"]) == 5   # 실측: speed·ph·beat·scm·vs
    assert len(txt["segments"][0]["extra_material_refs"]) == 1   # material_animation


def test_assets_to_copy_listed():
    _, assets = _build()
    reals = {r for r, _ in assets}
    assert reals == {r"C:\real\src.mp4", r"C:\real\b0.mp3", r"C:\real\b1.mp3"}


def test_text_content_is_json_string_with_text():
    draft, _ = _build()
    tm = draft["materials"]["texts"][0]
    assert isinstance(tm["content"], str) and '"text": "첫 장면"' in tm["content"]


def test_canvas_vertical_default():
    draft, _ = _build()
    assert draft["canvas_config"]["width"] == 1080 and draft["canvas_config"]["height"] == 1920


def test_missing_source_skips_video_but_keeps_audio_text():
    plan = {"beats": [{"beat_idx": 0, "role": "훅", "narration": "장면",
                       "primary": {"video_id": "gone", "start": 0.0, "end": 2.0}}]}
    draft, _ = cd.build_draft(plan=plan, timeline=[{"beat_idx": 0, "t0": 0.0, "dur": 2.0,
                              "narration": "장면", "role": "훅"}],
                              source_video_paths={}, tts_paths=_TTS, asset_paths=_ASSET,
                              project_name="x")
    types = {t["type"] for t in draft["tracks"]}
    assert "video" not in types and "audio" in types and "text" in types
