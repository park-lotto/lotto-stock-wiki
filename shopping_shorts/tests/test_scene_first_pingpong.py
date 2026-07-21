"""build_scene_first_plan의 ping_pong opt-in 배선 — 행위 어긋난 비트 화면을 스왑하나,
기본(off)이면 무변화(회귀0)."""
from shopping_shorts import edit_plan


_SOURCES = [
    {"video_id": "BB", "full_text": "백본", "segments": [
        {"seg_id": "BB-1", "start": 0, "end": 3, "text": "", "scene_desc": "팬케이크 뒤집는", "action": "뒤집다"}]},
    {"video_id": "S1", "full_text": "서브", "segments": [
        {"seg_id": "S1-9", "start": 0, "end": 3, "text": "", "scene_desc": "바나나 써는", "action": "자르다"}]},
]


def _fake_call(prompt, schema):
    # 후보 1개: 나레이션은 '자르다'(썰어), 화면은 BB-1('뒤집다') → 불일치
    return {"candidates": [{"beats": [
        {"seg_ids": ["BB-1"], "narration": "바나나 썰어 넣고", "fit": 5, "role": "방법"}]}]}


def test_pingpong_on_swaps_mismatched_screen():
    res = edit_plan.build_scene_first_plan(_SOURCES, "레퍼런스", 20, n_candidates=1,
                                           call=_fake_call, ping_pong=True)
    beat = res["candidates"][0]["plan"]["beats"][0]
    assert beat["primary"]["action"] == "자르다"      # 화면이 자르다 클립으로 스왑됨
    assert beat.get("action_fixed") is True


def test_pingpong_off_leaves_screen():
    res = edit_plan.build_scene_first_plan(_SOURCES, "레퍼런스", 20, n_candidates=1,
                                           call=_fake_call, ping_pong=False)
    beat = res["candidates"][0]["plan"]["beats"][0]
    assert beat["primary"]["seg_id"] == "BB-1"        # 기본: 원래 화면 그대로
    assert beat.get("action_fixed") is None
