"""안 쓴 소스 넣기 — s2=0(Gemini 선택편중) 해소.

카드 033(2026-09-29): 옛 ensure_sources_used는 primary를 갈아끼웠고 슬롯 경로에선 아예 안 돌았다.
주인 함수 backbone.finalize_scenes로 흡수하면서 계약이 바뀌었다 — **primary(대본이 지목한 화면)는
그대로 두고**, 안 쓴 소스의 클립을 alternate 자리에 넣는다(대사↔화면 싱크를 primary가 지킨다)."""
from shopping_shorts import backbone


def _seg(vid, sid, action, start=0.0, end=1.5):
    return {"video_id": vid, "seg_id": sid, "action": action, "start": start, "end": end,
            "text": "", "scene_desc": ""}


def _sources():
    return [
        {"video_id": "s0", "segments": [_seg("s0", "s0-1", "자르다"), _seg("s0", "s0-2", "뒤집다"),
                                        _seg("s0", "s0-3", "뒤집다", 3.0, 4.5)]},
        {"video_id": "s1", "segments": [_seg("s1", "s1-1", "뒤집다", 5.0, 6.5)]},
    ]


def _beats_all_s0():
    return [
        {"beat_idx": 0, "narration": "바나나를 썰어요", "fit": 5,
         "primary": _seg("s0", "s0-1", "자르다"), "alternates": []},
        {"beat_idx": 1, "narration": "이제 팬케이크를 뒤집어요", "fit": 5,
         "primary": _seg("s0", "s0-2", "뒤집다"), "alternates": [_seg("s0", "s0-3", "뒤집다", 3.0, 4.5)]},
    ]


def _all_vids(beats):
    return {c.get("video_id") for b in beats
            for c in [b.get("primary")] + list(b.get("alternates") or []) if c}


def test_forces_unused_source_into_alternate_primary_untouched():
    beats = _beats_all_s0()
    out = backbone.finalize_scenes(beats, _sources())
    assert "s1" in _all_vids(out)                                    # 안 쓰이던 s1이 화면에 들어옴
    assert [b["primary"]["seg_id"] for b in out] == ["s0-1", "s0-2"]  # primary 불변(싱크 보존)


def test_noop_when_all_used():
    beats = [
        {"beat_idx": 0, "narration": "썰어요", "fit": 5, "primary": _seg("s0", "s0-1", "자르다"),
         "alternates": []},
        {"beat_idx": 1, "narration": "뒤집어요", "fit": 5, "primary": _seg("s1", "s1-1", "뒤집다"),
         "alternates": []},
    ]
    out = backbone.finalize_scenes(beats, _sources())
    assert out == beats                                              # 무변경


def test_single_source_noop():
    srcs = [{"video_id": "s0", "segments": [_seg("s0", "s0-1", "자르다")]}]
    beats = [{"beat_idx": 0, "narration": "썰어요", "fit": 5,
              "primary": _seg("s0", "s0-1", "자르다"), "alternates": []}]
    assert backbone.finalize_scenes(beats, srcs) == beats
