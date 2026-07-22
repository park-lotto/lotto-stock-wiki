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


def test_backbone_base_prompt_carries_drama_and_bank():
    # 백본-베이스 대본생성 프롬프트에 짤드라마 헌장 + 강한오프너 규칙 + 은행부품이 실려야 한다
    # (안 실리면 흐름만 밋밋하게 따라가 설명체가 나온다 — 2026-07-22 대본 초기화 실사고).
    seen = {}

    def _cap(prompt, schema):
        if "beats" in schema.get("required", []):
            seen["prompt"] = prompt
            return {"beats": [{"narration": "훅", "seg_id": "BB-1"}]}
        return {"candidates": []}
    edit_plan.build_scene_first_plan(_SOURCES, "ref", 20, n_candidates=1,
                                     call=_cap, backbone_base=True,
                                     bank_context="[은행 훅 재료] 이거 실화냐")
    p = seen["prompt"]
    assert "짤드라마" in p                       # 짤드라마 헌장 주입
    assert "설명체" in p                         # 강한 오프너(설명체 금지) 규칙
    assert "이거 실화냐" in p                    # 은행 부품 주입
    assert "화면=행위, 대사=이야기" in p         # 중간 비트도 설명 말고 이야기로(핵심 규칙)
    assert "스토리 아크를 비트에 분배" in p       # 인물→긴장→반응 아크 강제(진짜 스토리짤)
    assert "인물이 중간·끝까지 관통" in p         # 세운 인물이 중간에 안 사라지게


def test_judge_picks_best_of_n_drafts():
    # 백본 순서 위에서 N개 안 생성 → 심사위원(대본품질)이 제일 좋은 걸 추천.
    state = {"i": 0}

    def _call(prompt, schema):
        props = schema.get("properties", {})
        if "script_quality" in props:                      # 심사 콜
            return {"script_quality": 5 if "좋은 훅" in prompt else 1,
                    "scene_sync": 3, "storyline": 3}
        state["i"] += 1                                     # 생성 콜: 초안마다 다르게
        if state["i"] == 1:
            return {"beats": [{"narration": "밋밋한 설명이에요", "seg_id": "BB-1"}]}
        return {"beats": [{"narration": "좋은 훅 이거 실화냐", "seg_id": "BB-2"}]}

    res = edit_plan.build_scene_first_plan(_SOURCES, "ref", 20, call=_call,
                                           backbone_base=True, judge=True)
    assert len(res["candidates"]) >= 2                      # best-of-N(중복 제거 후)
    rec = next(c for c in res["candidates"] if c["recommended"])
    assert "좋은 훅" in rec["plan"]["beats"][0]["narration"]   # 심사 최고점이 추천됨
    assert rec["judge"]["script_quality"] == 5


def test_backbone_base_off_is_reference_first():
    # backbone_base=False면 기존 레퍼런스-먼저 경로 그대로(회귀0).
    def _ref(prompt, schema):
        return {"candidates": [{"beats": [
            {"seg_ids": ["BB-1"], "narration": "레퍼런스 대본", "fit": 4, "role": "훅"}]}]}
    res = edit_plan.build_scene_first_plan(_SOURCES, "레퍼런스", 20, n_candidates=1,
                                           call=_ref, backbone_base=False)
    assert "레퍼런스 대본" in res["candidates"][0]["plan"]["beats"][0]["narration"]
