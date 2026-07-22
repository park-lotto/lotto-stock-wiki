from shopping_shorts.video_assemble import _effective_dur, _TRIM_FLOOR


def test_effective_dur_subtracts_both_edges():
    assert _effective_dur(5.0, head_trim=0.5, tail_trim=1.0) == 3.5


def test_effective_dur_no_trim_returns_probe():
    assert _effective_dur(4.2) == 4.2


def test_effective_dur_floor_guard_blocks_overtrim():
    # 과트림: 남는 길이가 floor 밑이면 floor로 고정(음수/역전 방지)
    assert _effective_dur(1.0, tail_trim=0.9, floor=0.4) == 0.4


def test_effective_dur_negative_trim_treated_as_zero():
    assert _effective_dur(3.0, head_trim=-1.0, tail_trim=-2.0) == 3.0
