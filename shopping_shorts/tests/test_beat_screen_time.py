"""비트별 화면 길이 하한 — 말하는 시간만큼 화면이 붙어야 한다(2026-07-31).

실측(job 61a2678a8e03): 말 31.9초 vs 화면 13.8초. 모자란 화면을 렌더가 다음 클립으로
메워 밀림이 누적됐고, "투명해서 답답하지 않아요"에 다음 비트의 계란 컷이 걸렸다.
"""
from shopping_shorts import edit_plan as ep


def _seg_map(n, dur=1.0, vid="A"):
    m = {}
    for i in range(n):
        sid = f"{vid}-{i}"
        m[sid] = {"video_id": vid, "seg_id": sid, "start": i * dur, "end": (i + 1) * dur,
                  "scene_desc": f"장면{i}", "change": "", "is_key": False, "shot_role": "기타"}
    return m


def _beat(sid, secs, seg_map, alts=()):
    return {"beat_idx": 0, "role": "해결", "narration": "가", "caption_lines": None,
            "target_seconds": secs, "effect": "cut",
            "primary": ep._ground_ref({"seg_id": sid}, seg_map),
            "alternates": [ep._ground_ref({"seg_id": s}, seg_map) for s in alts]}


def test_fills_until_screen_covers_narration():
    sm = _seg_map(10)
    beats = ep._fill_beat_screen_time([_beat("A-0", 4.0, sm)], sm)
    assert ep._beat_screen_secs(beats[0]) >= 4.0


def test_does_not_touch_beat_that_already_has_enough():
    sm = _seg_map(10)
    b = _beat("A-0", 1.0, sm)
    before = list(b["alternates"])
    beats = ep._fill_beat_screen_time([b], sm)
    assert beats[0]["alternates"] == before


def test_does_not_steal_clips_used_by_other_beats():
    """다른 비트가 쓰는 컷을 뺏으면 그쪽이 어긋난다 — 안 쓴 것부터 채운다."""
    sm = _seg_map(6)
    b0 = _beat("A-0", 3.0, sm)
    b1 = _beat("A-5", 1.0, sm)
    ep._fill_beat_screen_time([b0, b1], sm)
    used0 = {s["seg_id"] for s in b0["alternates"]}
    assert "A-5" not in used0


def test_prefers_same_source_video():
    sm = _seg_map(4, vid="A")
    sm.update(_seg_map(4, vid="B"))
    b = _beat("A-0", 3.0, sm)
    ep._fill_beat_screen_time([b], sm)
    assert b["alternates"] and b["alternates"][0]["video_id"] == "A"


def test_reuses_when_inventory_exhausted():
    """인벤토리가 동나면 재사용을 허용한다 — 빈 화면보다 낫다."""
    sm = _seg_map(2)
    b = _beat("A-0", 6.0, sm)
    ep._fill_beat_screen_time([b], sm)
    assert ep._beat_screen_secs(b) > 1.0        # 뭐라도 더 붙었다


def test_prompt_states_the_duration_rule():
    import inspect
    src = inspect.getsource(ep._scene_first_candidates)
    assert "길이 합이 그 대사를 읽는 시간 이상" in src
