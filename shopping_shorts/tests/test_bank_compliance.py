from shopping_shorts.bank_compliance import judge_compliance


def test_judge_compliance_returns_scores():
    captured = {}

    def fake_call(prompt, schema):
        captured["prompt"] = prompt
        return {"arc_follow": 4, "flavor_follow": 3, "verbatim_copy": False, "reason": "ok"}

    beats = [{"narration": "이거 대박"}, {"narration": "비법은"}]
    out = judge_compliance("★학습된 아크: 상황=요리\n[승인된 부품] 훅: h1", beats, call=fake_call)
    assert out["arc_follow"] == 4
    assert out["verbatim_copy"] is False
    assert "요리" in captured["prompt"]        # 주입 은행자료가 프롬프트에
    assert "비법은" in captured["prompt"]       # 생성 대본이 프롬프트에


def test_judge_compliance_clamps_and_none_on_failure():
    assert judge_compliance("ctx", [{"narration": "x"}], call=lambda p, s: None) is None
    out = judge_compliance("ctx", [{"narration": "x"}],
                           call=lambda p, s: {"arc_follow": 9, "flavor_follow": -2, "verbatim_copy": True})
    assert out["arc_follow"] == 5     # 0~5로 클램프
    assert out["flavor_follow"] == 0
    assert out["verbatim_copy"] is True


def test_judge_compliance_empty_beats_none():
    assert judge_compliance("ctx", [], call=lambda p, s: {"arc_follow": 3}) is None
