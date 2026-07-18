"""_caption_durations의 real_durs 합류 — 오면 쓰고, None/길이불일치면 현행 그대로."""
from shopping_shorts.video_assemble import _caption_durations, _caption_segments


def test_none_is_byte_identical_to_current():
    segs = ["여러분", "오이 절대", "냉장고에 그냥 두지 마세요"]
    base = _caption_durations(segs, 5.0)              # 현행
    same = _caption_durations(segs, 5.0, real_durs=None)
    assert same == base


def test_real_durs_used_when_given():
    segs = ["가", "나", "다"]
    out = _caption_durations(segs, 3.0, real_durs=[2.0, 0.5, 0.5])
    # 글자수 비례(균등 1.0/1.0/1.0)가 아니라 real 쪽으로 기운다.
    assert out[0] > out[1] and out[0] > out[2]
    assert abs(sum(out) - 3.0) < 1e-6


def test_length_mismatch_falls_back():
    segs = ["가", "나", "다"]
    base = _caption_durations(segs, 3.0)
    out = _caption_durations(segs, 3.0, real_durs=[2.0, 1.0])   # 길이 2 ≠ 3
    assert out == base


def test_min_dur_floor_still_applies_with_real():
    segs = ["가", "나"]
    out = _caption_durations(segs, 4.0, real_durs=[3.99, 0.01])
    assert min(out) >= 0.25 - 1e-9        # _CAP_MIN_DUR 하한 유지
    assert abs(sum(out) - 4.0) < 1e-6
