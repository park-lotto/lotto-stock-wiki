# -*- coding: utf-8 -*-
"""완성본 컷 = 편집 화면 컷(screen_clips) — 캐시에 화면 컷이 있으면 렌더 계획이 그대로 쓴다(2026-09-26 근본해결)."""
from shopping_shorts import screen_clips as sc
from shopping_shorts import video_assemble as va


def _beat():
    return {"beat_idx": 0, "phrase_sync": None, "narration": "가 나 다",
            "primary": {"video_id": "s0", "seg_id": "a", "start": 1.0, "end": 4.0}, "alternates": []}


def test_lookup_used_by_planner_and_scaled_to_tts():
    b = _beat()
    sc._CACHE[sc.beat_key(b)] = {"t": 2.0, "c": [{"v": "s0", "s": 1.0, "d": 1.2, "sd": 1.2, "fit": 0},
                                                 {"v": "s0", "s": 2.5, "d": 0.8, "sd": 0.6, "fit": 0}]}
    try:
        got = va.plan_beat_clips_for(b, 2.2, {"s0": 30.0})
        assert [(c["video_id"], c["start"]) for c in got] == [("s0", 1.0), ("s0", 2.5)]
        assert abs(sum(c["out_dur"] for c in got) - 2.2) < 1e-6          # 칸 길이는 렌더 음성 길이로 맞춘다
        assert "playback_speed" not in got[1]                              # 모자람 = 느리게+정지(화면 합본과 같은 기계)
        assert sc.has(b)
    finally:
        sc._CACHE.pop(sc.beat_key(b), None)


def test_missing_source_falls_back_to_calculation():
    b = _beat()
    sc._CACHE[sc.beat_key(b)] = {"t": 2.0, "c": [{"v": "s9", "s": 0.0, "d": 2.0, "sd": 2.0, "fit": 0}]}
    try:
        got = va.plan_beat_clips_for(b, 2.0, {"s0": 30.0})
        assert got and all(c["video_id"] == "s0" for c in got)            # 못 읽는 소스면 종전 계산
    finally:
        sc._CACHE.pop(sc.beat_key(b), None)


def test_clean_replay_beat_ignores_screen_cache():
    b = dict(_beat(), phrase_sync=False, clean_replay=True,
             manual_cuts=[{"video_id": "clean", "seg_id": "clean-0", "start": 5.0, "dur": 2.0, "sdur": 2.0}],
             scene_override=[{"video_id": "clean", "seg_id": "clean-0", "start": 5.0, "end": 7.0}])
    sc._CACHE[sc.beat_key(b)] = {"t": 2.0, "c": [{"v": "s0", "s": 1.0, "d": 2.0, "sd": 2.0, "fit": 0}]}
    try:
        got = va.plan_beat_clips_for(b, 2.0, {"clean": 30.0})
        assert [c["video_id"] for c in got] == ["clean"]
    finally:
        sc._CACHE.pop(sc.beat_key(b), None)
