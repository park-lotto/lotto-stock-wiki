from shopping_shorts import edit_plan


def _fake_call(prompt, schema, **kw):
    # 프롬프트에 헌장·팔레트가 실렸는지 + 후보 형태 반환
    assert "스토리라인" in prompt and "[s0-0]" in prompt and "레퍼" in prompt
    return {"candidates": [{
        "hook": "양파 이렇게 두지 마세요",
        "story_person": "살림고수", "story_event": "썩는 양파 발견",
        "story_resolution": "통풍보관 터득", "cta_line": "댓글에 '보관법'", "cta_keyword": "보관법",
        "beats": [{"role": "훅", "narration": "곰팡이 핀 양파 보셨죠?", "seg_ids": ["s0-1", "s0-2"], "fit": 5, "forced": False}]}]}


def test_scene_first_candidates_shape():
    cands = edit_plan._scene_first_candidates("[s0-0] 화면:양파\n[s0-1] 화면:곰팡이\n[s0-2] 화면:단면",
                                              reference_text="원본대본 텍스트", target_seconds=20,
                                              n=3, call=_fake_call)
    assert len(cands) == 1
    assert cands[0]["cta_keyword"] == "보관법"
    assert cands[0]["beats"][0]["seg_ids"] == ["s0-1", "s0-2"]


def test_scene_first_candidates_fail_open():
    assert edit_plan._scene_first_candidates("[s0-0] 화면:양파", "ref", 20, call=lambda *a, **k: None) == []


def _seg_map():
    def s(sid, st, en, sc):
        return {"video_id": sid.split("-")[0], "seg_id": sid, "start": st, "end": en,
                "text": "", "scene_desc": sc}
    return {x["seg_id"]: x for x in [
        s("s0-1", 1.0, 2.0, "곰팡이"), s("s0-2", 2.0, 3.5, "단면"), s("s0-3", 4.0, 6.0, "통풍")]}


def test_ground_candidate_multicut_to_edl():
    cand = {"beats": [
        {"role": "훅", "narration": "곰팡이 핀 양파 보셨죠?", "seg_ids": ["s0-1", "s0-2"], "fit": 5, "forced": False},
        {"role": "해결", "narration": "통풍이 핵심이에요 진짜", "seg_ids": ["s0-3"], "fit": 4, "forced": True}]}
    plan = edit_plan._ground_candidate(cand, _seg_map())
    b0 = plan["beats"][0]
    assert b0["primary"]["seg_id"] == "s0-1"                      # 첫 seg=primary
    assert [a["seg_id"] for a in b0["alternates"]] == ["s0-2"]     # 나머지=alternates(다중컷)
    assert b0["primary"]["scene_desc"] == "곰팡이"                 # scene_desc 실림
    assert plan["beats"][1]["forced"] is True and plan["beats"][1]["fit"] == 4
    assert b0["target_seconds"] > 0                                # 글자수 기준 재계산됨


def test_ground_candidate_drops_invalid_primary():
    cand = {"beats": [{"role": "x", "narration": "n", "seg_ids": ["없는id"], "fit": 3, "forced": False}]}
    assert edit_plan._ground_candidate(cand, _seg_map()) is None   # 유효 비트 0개 → None
