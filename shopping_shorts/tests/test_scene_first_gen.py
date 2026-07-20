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
