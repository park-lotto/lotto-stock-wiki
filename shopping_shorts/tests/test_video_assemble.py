from shopping_shorts import video_assemble as va


def test_pick_segment_primary_covers_narration():
    # primary 구간 3초, tts 2.4초 → primary가 1배속으로 담을 수 있으므로 primary 선택
    beat = {"primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 3.0}, "alternates": []}
    ref = va._pick_segment(beat, tts_dur=2.4, source_video_paths={"A": "a.mp4"})
    assert ref["seg_id"] == "A-0"


def test_pick_segment_prefers_alternate_that_covers_when_primary_too_short():
    # primary 1초로 tts 2.4초를 못 담음 → 2.4초를 담을 수 있는 alternate(3초) 선택
    beat = {
        "primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 1.0},
        "alternates": [{"video_id": "B", "seg_id": "B-0", "start": 0.0, "end": 3.0}],
    }
    ref = va._pick_segment(beat, tts_dur=2.4, source_video_paths={"A": "a.mp4", "B": "b.mp4"})
    assert ref["seg_id"] == "B-0"


def test_pick_segment_picks_longest_when_none_cover():
    # 아무 후보도 tts를 못 담으면 가장 긴 후보 선택(부족분은 루프로 채움)
    beat = {
        "primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 1.0},
        "alternates": [{"video_id": "B", "seg_id": "B-0", "start": 0.0, "end": 2.0}],
    }
    ref = va._pick_segment(beat, tts_dur=5.0, source_video_paths={"A": "a.mp4", "B": "b.mp4"})
    assert ref["seg_id"] == "B-0"  # 2초 > 1초


def test_pick_segment_skips_missing_source():
    # primary 소스가 없으면 존재하는 alternate로
    beat = {
        "primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 5.0},
        "alternates": [{"video_id": "B", "seg_id": "B-0", "start": 0.0, "end": 3.0}],
    }
    ref = va._pick_segment(beat, tts_dur=2.0, source_video_paths={"B": "b.mp4"})
    assert ref["seg_id"] == "B-0"
