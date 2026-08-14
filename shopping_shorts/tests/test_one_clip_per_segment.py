"""1장 = 1컷 모드 — 2026-08-14 사장님 "1 2 3 - 1로 되돌아오던데 코드인가".

라운드로빈은 소재가 모자라면 앞 장면으로 되돌아와 같은 장면이 두 번 나온다(실측 결과 칸:
담김 3장인데 컷은 4개, 4번째가 1번 장면의 뒷부분). 이 모드는 담은 순서대로 한 장에 한 컷만
쓰고, 길이는 나레이션을 장수로 고르게 나눠 준다.

★실험실이 아니라 **렌더에** 넣는다 — 실험실에만 넣으면 미리보기와 실제 영상이 갈린다
(0순위-B). 기본은 off라 켜기 전까지 결과가 바뀌지 않는다.
"""
from shopping_shorts.video_assemble import _plan_beat_clips


def _seg(vid, start, end):
    return {"video_id": vid, "start": start, "end": end}


def test_no_return_to_earlier_segment():
    """되돌아옴 없음 — 담은 장수만큼만 컷이 나온다."""
    segs = [_seg("s0", 4.7, 8.8), _seg("s0", 16.7, 18.6), _seg("s3", 2.8, 4.6)]
    clips = _plan_beat_clips(segs, 7.3, max_shot=2.2, one_per_seg=True)
    assert len(clips) == 3
    assert [c["start"] for c in clips] == [4.7, 16.7, 2.8]


def test_round_robin_still_returns_by_default():
    """기본(off)은 종전 그대로 — 소재가 모자라면 앞 장면으로 되돌아온다(회귀 0)."""
    segs = [_seg("s0", 4.7, 8.8), _seg("s0", 16.7, 18.6), _seg("s3", 2.8, 4.6)]
    clips = _plan_beat_clips(segs, 7.3, max_shot=2.2)
    assert len(clips) > len(segs)                      # 되돌아와 컷이 더 많다
    assert clips[-1]["start"] > clips[0]["start"]      # 1번 장면의 뒷부분을 이어 쓴다


def test_share_is_even_when_sources_long_enough():
    """장면이 넉넉하면 나레이션을 장수로 고르게 나눈다."""
    segs = [_seg("a", 0, 10), _seg("b", 0, 10), _seg("c", 0, 10)]
    clips = _plan_beat_clips(segs, 6.0, max_shot=2.2, one_per_seg=True)
    assert len(clips) == 3
    assert all(abs(c["out_dur"] - 2.0) < 1e-6 for c in clips)


def test_proportional_shrink():
    """총합이 남으면 길이 비례로 줄인다 — 긴 장면은 길게, 짧은 장면은 짧게."""
    segs = [_seg("a", 0, 2.0), _seg("b", 0, 4.0)]
    clips = _plan_beat_clips(segs, 3.0, max_shot=2.2, one_per_seg=True)
    assert len(clips) == 2
    assert abs(clips[0]["out_dur"] - 1.0) < 1e-6       # 2:4 비율 그대로
    assert abs(clips[1]["out_dur"] - 2.0) < 1e-6


def test_proportional_stretch():
    """모자라면 비례로 늘린다 — 마지막 하나만 길게 늘리지 않는다."""
    segs = [_seg("a", 0, 2.0), _seg("b", 0, 4.0)]
    clips = _plan_beat_clips(segs, 12.0, max_shot=2.2, one_per_seg=True)
    assert abs(clips[0]["out_dur"] - 4.0) < 1e-6
    assert abs(clips[1]["out_dur"] - 8.0) < 1e-6


def test_too_small_share_is_dropped():
    """비례로 나눴을 때 0.8초에 못 미치는 장면은 빼고 남은 것끼리 다시 나눈다(깜빡임 방지)."""
    segs = [_seg("a", 0, 1.0), _seg("b", 0, 10)]      # a 몫은 0.55초 → 제외
    clips = _plan_beat_clips(segs, 6.0, max_shot=2.2, one_per_seg=True)
    assert [c["video_id"] for c in clips] == ["b"]
    assert abs(clips[0]["out_dur"] - 6.0) < 1e-6


def test_tiny_leftover_not_made_into_clip():
    """0.8초 미만 조각은 새 컷으로 만들지 않는다(깜빡임 방지) — 첫 컷은 예외 없이 만든다."""
    segs = [_seg("a", 0, 10), _seg("b", 0, 0.3)]
    clips = _plan_beat_clips(segs, 6.0, max_shot=2.2, one_per_seg=True)
    assert [c["video_id"] for c in clips] == ["a"]


def test_single_segment():
    segs = [_seg("a", 0, 10)]
    clips = _plan_beat_clips(segs, 4.0, max_shot=2.2, one_per_seg=True)
    assert len(clips) == 1 and abs(clips[0]["out_dur"] - 4.0) < 1e-6

