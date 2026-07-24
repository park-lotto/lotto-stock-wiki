"""fit 정직화(2026-07-22 페이블): fit은 Gemini 자기채점이라 전부 5/5 — 행위 증거로 깎아
스왑버튼(fit≤2)·약비트 재작성(fit≤3)·추천점수(avg_fit)가 실제로 작동하게."""
from shopping_shorts import edit_plan


_SOURCES = [
    {"video_id": "BB", "full_text": "", "segments": [
        {"seg_id": "BB-1", "start": 0, "end": 3, "text": "", "scene_desc": "팬케이크 뒤집는", "action": "뒤집다"},
        {"seg_id": "BB-2", "start": 3, "end": 6, "text": "", "scene_desc": "완성 접시", "action": ""}]},
]


def test_verify_fits_caps_action_mismatch():
    beats = [{"narration": "바나나 썰어 넣고", "fit": 5,
              "primary": {"seg_id": "BB-1", "action": "뒤집다", "scene_desc": ""}}]
    out = edit_plan._verify_fits(beats)
    assert out[0]["fit"] == 2                       # 자기신고 5 → 증거로 2
    assert out[0]["fit_evidence"] == "action_mismatch"


def test_verify_fits_holds_when_ambiguous():
    # 화면 행위 미검출(결과컷) → 판정 보류(오탐 없음).
    beats = [{"narration": "바나나 썰어 넣고", "fit": 5,
              "primary": {"seg_id": "BB-2", "action": "", "scene_desc": "완성 접시"}}]
    assert edit_plan._verify_fits(beats)[0]["fit"] == 5


def test_grounded_candidates_get_honest_fit():
    # 생성이 fit5로 우겨도 grounding 후 어긋난 비트는 2로 내려간다(ping_pong off 경로).
    def _call(prompt, schema):
        return {"candidates": [{"hook": "", "beats": [
            {"role": "", "narration": "바나나 썰어 넣고", "seg_ids": ["BB-1"], "fit": 5}]}]}
    res = edit_plan.build_scene_first_plan(_SOURCES, "ref", 20, n_candidates=1,
                                           call=_call, ping_pong=False)
    assert res["candidates"][0]["plan"]["beats"][0]["fit"] == 2
