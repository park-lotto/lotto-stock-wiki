"""컷 리듬 + 전역 반복 해소 + 포인트 홀드 + 비주얼 풀(2026-07-22 페이블 진단 job 23a6db67333a:
비트당 6.8컷 파편·B롤 체인 5비트 반복·포인트 장면 묻힘)."""
from shopping_shorts import backbone


def _seg(sid, dur, vid="s0", action=None, desc=""):
    return {"seg_id": sid, "video_id": vid, "start": 0, "end": dur,
            "action": action, "scene_desc": desc}


def _pool(segs):
    return [{"video_id": "s0", "full_text": "", "segments": segs}]


def test_is_point_beat():
    assert backbone.is_point_beat({"narration": "마지막으로 비법 소스를 듬뿍 얹어줍니다"}) is True
    assert backbone.is_point_beat({"narration": "겉은 바삭한데 속은 촉촉해요"}) is False


def test_fill_caps_clip_count():
    # 대사 10초인데 파편이 많아도 상한(3)까지만 붙인다 → 뚝뚝 끊김 방지.
    segs = [_seg(f"s0-{i}", 0.6) for i in range(10)]
    beat = {"narration": "긴 대사", "primary": _seg("s0-p", 0.6),
            "alternates": []}
    out = backbone.fill_clips_to_cover(beat, _pool(segs), need=10.0, max_clips=3)
    assert 1 + len(out["alternates"]) <= 3          # primary+alternates ≤ 3


def test_fill_prefers_longer_clips():
    # 같은 소스 안에서 긴 컷을 먼저 붙인다(파편 억제).
    segs = [_seg("short", 0.5), _seg("long", 2.5), _seg("mid", 1.5)]
    beat = {"narration": "x", "primary": _seg("s0-p", 0.5), "alternates": []}
    out = backbone.fill_clips_to_cover(beat, _pool(segs), need=3.0, max_clips=3)
    assert out["alternates"][0]["seg_id"] == "long"


def test_visual_score_prefers_tasty_scenes():
    assert backbone._visual_score({"scene_desc": "치즈가 늘어나는 완성 클로즈업"}) >= 2
    assert backbone._visual_score({"scene_desc": "재료 손질"}) == 0


def test_dedup_clips_global_removes_repeated_alternates():
    # 같은 B롤(s0-2)이 두 비트 alternates에 반복 → 두 번째는 안 쓴 것으로 교체 or 드롭.
    fresh = [_seg("s0-9", 1.5, desc="완성"), _seg("s0-8", 1.5, desc="클로즈업")]
    pool = _pool([_seg("s0-2", 1.5), _seg("s0-3", 1.5)] + fresh)
    beats = [
        {"narration": "a", "primary": _seg("s0-0", 1.5), "alternates": [_seg("s0-2", 1.5)]},
        {"narration": "b", "primary": _seg("s0-1", 1.5), "alternates": [_seg("s0-2", 1.5)]},
    ]
    out = backbone.dedup_clips_global(beats, pool)
    all_alts = [a["seg_id"] for b in out for a in b["alternates"]]
    assert all_alts.count("s0-2") <= 1              # 반복 제거


def test_dedup_clips_global_caps_clips():
    pool = _pool([_seg(f"s0-{i}", 1.5) for i in range(8)])
    beat = {"narration": "a", "primary": _seg("s0-0", 1.5),
            "alternates": [_seg(f"s0-{i}", 1.5) for i in range(1, 6)]}
    out = backbone.dedup_clips_global([beat], pool)
    assert 1 + len(out[0]["alternates"]) <= 3       # 상한
