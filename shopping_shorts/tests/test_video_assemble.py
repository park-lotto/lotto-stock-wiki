from shopping_shorts import video_assemble as va


def test_pick_segment_primary_fits():
    # primary 구간 3초, tts 2.4초 → 배속 2.4/3=0.8 (하한 정확히 OK)
    beat = {"primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 3.0}, "alternates": []}
    ref, rate = va._pick_segment(beat, tts_dur=2.4, source_video_paths={"A": "a.mp4"})
    assert ref["seg_id"] == "A-0"
    assert abs(rate - 0.8) < 1e-6


def test_pick_segment_falls_back_to_alternate_when_primary_too_short():
    # primary 1초인데 tts 2.4초면 배속 2.4(>1.2 한도초과) → alternate로
    beat = {
        "primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 1.0},
        "alternates": [{"video_id": "B", "seg_id": "B-0", "start": 0.0, "end": 3.0}],
    }
    ref, rate = va._pick_segment(beat, tts_dur=2.4, source_video_paths={"A": "a.mp4", "B": "b.mp4"})
    assert ref["seg_id"] == "B-0"
    assert 0.8 <= rate <= 1.2


def test_pick_segment_clamps_when_source_longer_than_tts():
    # primary 5초, tts 2초 → 그냥 2초만 잘라 씀(rate=1.0, 트림)
    beat = {"primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 5.0}, "alternates": []}
    ref, rate = va._pick_segment(beat, tts_dur=2.0, source_video_paths={"A": "a.mp4"})
    assert ref["seg_id"] == "A-0"
    assert abs(rate - 1.0) < 1e-6


def test_pick_segment_no_candidate_uses_primary_best_effort():
    # primary만 있고 너무 짧아도, alternate 없으면 primary를 최대배속으로 반환(드롭 안 함)
    beat = {"primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 0.5}, "alternates": []}
    ref, rate = va._pick_segment(beat, tts_dur=2.4, source_video_paths={"A": "a.mp4"})
    assert ref["seg_id"] == "A-0"
    assert rate == 1.2  # 최대 배속으로 클램프
