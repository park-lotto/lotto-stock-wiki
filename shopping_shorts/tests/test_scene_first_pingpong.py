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


def test_pingpong_on_swaps_mismatched_screen(monkeypatch):
    """★옛 경로(리라이트 믹스 off) 전용이다(2026-07-31).

    리라이트 믹스에서는 **말이 그 화면에서 나온 말**이라 화면 스왑이 필요 없고, 오히려
    코드가 못박은 원본 순서를 깬다(실측 job e288f2f0c387: 핑퐁 후처리가 화면을 다시
    뒤섞어 한 비트에 s0-1·s1-7·s1-13이 엉켰다). 그래서 새 경로는 마지막에 화면을 원본
    순서로 되돌린다. 이 테스트는 그 이전 경로의 스왑 동작을 계속 지킨다.
    """
    monkeypatch.setattr(edit_plan, "REWRITE_MIX", False)
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
