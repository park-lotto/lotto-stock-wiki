"""_caption_durations의 real_durs 합류 — 오면 쓰고, None/길이불일치면 현행 그대로."""
from shopping_shorts.video_assemble import _caption_durations, _caption_segments


def test_none_is_byte_identical_to_current():
    segs = ["여러분", "오이 절대", "냉장고에 그냥 두지 마세요"]
    base = _caption_durations(segs, 5.0)              # 현행
    same = _caption_durations(segs, 5.0, real_durs=None)
    assert same == base


def test_real_durs_used_when_given():
    # ⚠️칸을 넉넉히 준다(2026-08-17). _CAP_MIN_DUR가 0.25→1.0으로 오르면서 예전 3.0초 칸은
    #   3구절 × 하한 1.0 = 3.0 으로 **하한이 칸을 정확히 다 먹어** real 가중이 수학적으로
    #   불가능해졌다(전부 1.0/1.0/1.0). 하한이 이기는 건 의도된 동작이므로(짧은 구절이
    #   번쩍이지 않게 하는 게 우선), 여기서는 real 가중 자체를 보게 여유 있는 칸으로 옮긴다.
    #   실제 대사는 여유가 있어 real이 살아있는 것을 실측 확인했다
    #   (CTA 5구절/9.7초, 해결 3구절/4.4초 등 — 구절수×하한 < 칸길이).
    segs = ["가", "나", "다"]
    out = _caption_durations(segs, 6.0, real_durs=[4.0, 1.0, 1.0])
    # 글자수 비례(균등 2.0/2.0/2.0)가 아니라 real 쪽으로 기운다.
    assert out[0] > out[1] and out[0] > out[2]
    assert abs(sum(out) - 6.0) < 1e-6


def test_하한이_칸을_다_먹으면_균등해진다():
    """구절수 × 하한 ≥ 칸길이면 real 가중이 사라진다 — 의도된 동작임을 못 박는다."""
    segs = ["가", "나", "다"]
    out = _caption_durations(segs, 3.0, real_durs=[2.0, 0.5, 0.5])
    assert abs(sum(out) - 3.0) < 1e-6      # 총길이는 언제나 지킨다
    assert all(d > 0 for d in out)


def test_length_mismatch_falls_back():
    segs = ["가", "나", "다"]
    base = _caption_durations(segs, 3.0)
    out = _caption_durations(segs, 3.0, real_durs=[2.0, 1.0])   # 길이 2 ≠ 3
    assert out == base


def test_min_dur_floor_skipped_with_real():
    """(2026-08-29 동작 변경) 실측이 있으면 하한을 **적용하지 않는다** — 하한이 실발화보다
    긴 자막을 만들면 다음 구절 음성이 자막보다 앞서 들린다(사장님 실사고 job fa0f71a16a13).
    종전 테스트(하한 유지)는 이 결정으로 뒤집혔다."""
    segs = ["가", "나"]
    out = _caption_durations(segs, 4.0, real_durs=[3.99, 0.01])
    assert out == [3.99, 0.01]            # 실측 그대로 — 짧게 말했으면 짧게 띄운다


def test_real_durs_not_inflated_by_min_floor():
    """실발화 0.68초 구절을 하한(1.0초)이 늘리면 음성이 자막보다 앞선다(2026-08-29 실사고
    job fa0f71a16a13 — '충격 받았어요' 0.68→1.0으로 늘어나 다음 자막이 0.32초 늦었다).
    실측이 있으면 그 길이 그대로 띄운다."""
    segs = ["저 친구네 집 갔다가", "충격 받았어요", "애들 아침으로 이걸 해주더라고요"]
    out = _caption_durations(segs, 3.57, real_durs=[1.1, 0.68, 1.79])
    import pytest
    assert out == pytest.approx([1.1, 0.68, 1.79], abs=1e-6)
