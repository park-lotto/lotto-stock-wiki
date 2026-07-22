"""백본-베이스(확정스펙 2026-07-21): build_scene_first_plan(backbone_base=True)는 레퍼런스
자유생성 대신 백본 흐름 위에 100% 우리 대본을 생성한다(실제 seg_id만). 못 고르면 폴백."""
from shopping_shorts import edit_plan


# BB는 세그먼트 2개(최다) → 백본으로 뽑힌다. S1은 서브.
_SOURCES = [
    {"video_id": "BB", "full_text": "백본대본", "segments": [
        {"seg_id": "BB-1", "start": 0, "end": 3, "text": "", "scene_desc": "재료 손질", "action": "자르다"},
        {"seg_id": "BB-2", "start": 3, "end": 6, "text": "", "scene_desc": "완성 접시", "action": "올리다"}]},
    {"video_id": "S1", "full_text": "서브대본", "segments": [
        {"seg_id": "S1-9", "start": 0, "end": 3, "text": "", "scene_desc": "붓는 장면", "action": "붓다"}]},
]


def _bb_call(prompt, schema):
    # 백본 대본생성 스키마(beats: narration+seg_id) — 실제 seg_id(BB-1)와 없는 seg_id(ZZ-9) 섞음.
    return {"beats": [
        {"narration": "이거 진짜 대박인데요, 이렇게 썰기만 하면 끝나요", "seg_id": "BB-1"},
        {"narration": "짜잔, 이렇게 완성됩니다", "seg_id": "BB-2"},
        {"narration": "없는 장면 요구", "seg_id": "ZZ-9"}]}


def test_backbone_base_uses_backbone_script():
    res = edit_plan.build_scene_first_plan(_SOURCES, "레퍼런스무시", 20, n_candidates=3,
                                           call=_bb_call, backbone_base=True)
    assert len(res["candidates"]) == 1
    beats = res["candidates"][0]["plan"]["beats"]
    # 우리가 생성한 백본 대본이 실렸다(레퍼런스 자유생성 아님).
    assert "썰기만 하면" in beats[0]["narration"]
    # 인벤토리 밖 seg_id(ZZ-9)는 드롭 — 없는 장면 요구 차단.
    assert all(b["primary"]["seg_id"] in ("BB-1", "BB-2") for b in beats)


def test_backbone_base_falls_back_when_no_beats():
    # 백본 대본생성이 비면(빈 beats) 레퍼런스-먼저로 폴백해야 한다(회귀0).
    def _empty_bb(prompt, schema):
        if "beats" in schema.get("required", []):
            return {"beats": []}                       # 백본 생성 실패
        return {"candidates": [{"beats": [            # 레퍼런스-먼저 후보
            {"seg_ids": ["BB-1"], "narration": "폴백 대본", "fit": 4, "role": "훅"}]}]}
    res = edit_plan.build_scene_first_plan(_SOURCES, "레퍼런스", 20, n_candidates=1,
                                           call=_empty_bb, backbone_base=True)
    assert res["candidates"]
    assert "폴백" in res["candidates"][0]["plan"]["beats"][0]["narration"]


def test_backbone_base_off_is_reference_first():
    # backbone_base=False면 기존 레퍼런스-먼저 경로 그대로(회귀0).
    def _ref(prompt, schema):
        return {"candidates": [{"beats": [
            {"seg_ids": ["BB-1"], "narration": "레퍼런스 대본", "fit": 4, "role": "훅"}]}]}
    res = edit_plan.build_scene_first_plan(_SOURCES, "레퍼런스", 20, n_candidates=1,
                                           call=_ref, backbone_base=False)
    assert "레퍼런스 대본" in res["candidates"][0]["plan"]["beats"][0]["narration"]
