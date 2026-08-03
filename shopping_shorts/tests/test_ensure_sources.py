"""P1 서브 의무삽입 — s2=0(Gemini 선택편중) 해소.
dedup_and_balance는 '반복'만 고치지 '아예 안 씀'은 못 잡는다. 안 쓰인 소스의 클립을
같은 행위(narration↔clip)로 강제 삽입해 모든 소스가 최소 1회 화면에 뜨게 한다(sync 보존)."""
from shopping_shorts import backbone


def _seg(vid, sid, action, start=0.0, end=1.5):
    return {"video_id": vid, "seg_id": sid, "action": action, "start": start, "end": end,
            "text": "", "scene_desc": ""}


def _sources():
    # s0: 두 조각(자르다·뒤집다), s1: 뒤집다 조각 하나(우승작인데 안 쓰일 위험)
    return [
        {"video_id": "s0", "segments": [_seg("s0", "s0-1", "자르다"), _seg("s0", "s0-2", "뒤집다")]},
        {"video_id": "s1", "segments": [_seg("s1", "s1-1", "뒤집다")]},
    ]


def _beats_all_s0():
    # 둘 다 s0만 씀 → s1=0. 두 번째 비트 나레이션 행위=뒤집다(s1에 같은 행위 있음)
    return [
        {"beat_idx": 0, "narration": "바나나를 썰어요", "fit": 5,
         "primary": _seg("s0", "s0-1", "자르다"), "alternates": []},
        {"beat_idx": 1, "narration": "이제 팬케이크를 뒤집어요", "fit": 5,
         "primary": _seg("s0", "s0-2", "뒤집다"), "alternates": []},
    ]


def test_ensure_forces_unused_source_in():
    out = backbone.ensure_sources_used(_beats_all_s0(), _sources())
    used = {(b.get("primary") or {}).get("video_id") for b in out}
    assert "s1" in used   # 안 쓰이던 s1이 화면에 들어옴
    # 행위 매칭으로 교체됐으니 뒤집다 비트가 s1 조각으로 바뀜
    swapped = [b for b in out if (b.get("primary") or {}).get("video_id") == "s1"]
    assert swapped and swapped[0].get("forced_source") is True


def test_ensure_noop_when_all_used():
    beats = [
        {"beat_idx": 0, "narration": "썰어요", "fit": 5, "primary": _seg("s0", "s0-1", "자르다"),
         "alternates": []},
        {"beat_idx": 1, "narration": "뒤집어요", "fit": 5, "primary": _seg("s1", "s1-1", "뒤집다"),
         "alternates": []},
    ]
    out = backbone.ensure_sources_used(beats, _sources())
    assert [(b.get("primary") or {}).get("seg_id") for b in out] == ["s0-1", "s1-1"]  # 무변경


def test_ensure_no_action_match_leaves_untouched():
    # s1 조각 행위(끓이다)가 어느 비트 나레이션과도 안 맞으면 억지삽입 안 함(sync 보존)
    srcs = [
        {"video_id": "s0", "segments": [_seg("s0", "s0-1", "자르다"), _seg("s0", "s0-2", "자르다")]},
        {"video_id": "s1", "segments": [_seg("s1", "s1-1", "끓이다")]},
    ]
    beats = [
        {"beat_idx": 0, "narration": "썰어요", "fit": 5, "primary": _seg("s0", "s0-1", "자르다"),
         "alternates": []},
        {"beat_idx": 1, "narration": "또 썰어요", "fit": 5, "primary": _seg("s0", "s0-2", "자르다"),
         "alternates": []},
    ]
    out = backbone.ensure_sources_used(beats, srcs)
    assert all((b.get("primary") or {}).get("video_id") == "s0" for b in out)  # 억지 삽입 안 함


def test_ensure_single_source_noop():
    srcs = [{"video_id": "s0", "segments": [_seg("s0", "s0-1", "자르다")]}]
    beats = [{"beat_idx": 0, "narration": "썰어요", "fit": 5,
              "primary": _seg("s0", "s0-1", "자르다"), "alternates": []}]
    assert backbone.ensure_sources_used(beats, srcs) == beats
