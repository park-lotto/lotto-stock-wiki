"""게이트 교정 재픽(2026-07-25) — primary 비트 간 연속재생을 비연속·미사용소스로 끊는다.
is_continuous가 지금까지 alternates(dedup_clips_global)만 봐서 primary 연속(s0-4~s0-5)이
샜다(job 57ec653ba579 실사고). repick_for_gate가 그 절반을 막는다."""
from shopping_shorts import backbone


def _seg(vid, sid, start, end, action="굽다"):
    return {"video_id": vid, "seg_id": sid, "start": start, "end": end, "action": action}


_POOL = [
    {"video_id": "s0", "segments": [
        _seg("s0", "s0-4", 4.0, 6.0), _seg("s0", "s0-5", 6.0, 8.4),
        _seg("s0", "s0-1", 1.0, 2.0)]},
    {"video_id": "s1", "segments": [
        _seg("s1", "s1-0", 0.0, 2.5), _seg("s1", "s1-1", 2.5, 5.0)]},
]


def _beats_continuous():
    return [
        {"beat_idx": 0, "narration": "굽는다", "primary": _seg("s0", "s0-4", 4.0, 6.0), "alternates": []},
        {"beat_idx": 1, "narration": "더 굽는다", "primary": _seg("s0", "s0-5", 6.0, 8.4), "alternates": []},
    ]


def test_breaks_continuous_primary_run_using_unused_source():
    out = backbone.repick_for_gate(_beats_continuous(), _POOL, {})
    assert not backbone.is_continuous(out[0]["primary"], out[1]["primary"])
    assert any(b["primary"]["video_id"] == "s1" for b in out)  # 놀던 s1 동원


def test_original_beats_not_mutated():
    beats = _beats_continuous()
    before = beats[1]["primary"]["seg_id"]
    backbone.repick_for_gate(beats, _POOL, {})
    assert beats[1]["primary"]["seg_id"] == before


def test_point_beat_primary_untouched():
    beats = [
        {"beat_idx": 0, "narration": "굽는다", "primary": _seg("s0", "s0-4", 4.0, 6.0), "alternates": []},
        {"beat_idx": 1, "narration": "비법소스를 얹는다",
         "primary": _seg("s0", "s0-5", 6.0, 8.4, action="얹다"), "alternates": []},
    ]
    out = backbone.repick_for_gate(beats, _POOL, {})
    assert out[1]["primary"]["seg_id"] == "s0-5"  # 포인트 primary 유지
    assert not backbone.is_continuous(out[0]["primary"], out[1]["primary"])


def test_thin_pool_leaves_run_and_terminates():
    thin = [{"video_id": "s0", "segments": [_seg("s0", "s0-4", 4.0, 6.0), _seg("s0", "s0-5", 6.0, 8.4)]}]
    out = backbone.repick_for_gate(_beats_continuous(), thin, {})
    assert len(out) == 2  # 안 죽고 반환
