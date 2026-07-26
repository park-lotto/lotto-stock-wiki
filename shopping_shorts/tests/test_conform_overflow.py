"""후보 총 나레이션이 목표초 초과면 conform으로 줄인다(있는 conform_narration 배선)."""
from shopping_shorts import edit_plan


def _beat(narr):
    return {"narration": narr, "target_seconds": len(narr.replace(" ", "")) / 5.7,
            "primary": {"seg_id": "x"}, "alternates": [], "role": "", "fit": 4}


def _fake_conform(narr, target_seconds):
    # 목표 글자수로 앞에서 잘라 압축 흉내(결정적, Gemini 없음)
    budget = max(6, int(target_seconds * 5.7))
    compact = narr.replace(" ", "")
    return compact[:budget] if len(compact) > budget else None


def test_overflow_gets_conformed():
    # 목표 10초=57자인데 총 120자 → 초과 → 줄어야
    beats = [_beat("가" * 60), _beat("나" * 60)]
    out = edit_plan._conform_overflow_beats(beats, 10, conform=_fake_conform)
    total = sum(len(b["narration"].replace(" ", "")) for b in out)
    assert total < 120                     # 줄었다
    assert total <= 10 * 5.7 * 1.3         # 대략 예산 근처


def test_within_budget_unchanged():
    beats = [_beat("가" * 20), _beat("나" * 20)]   # 40자, 목표 10초=57자 이내
    out = edit_plan._conform_overflow_beats(beats, 10, conform=_fake_conform)
    assert [b["narration"] for b in out] == [b["narration"] for b in beats]  # 무변경


def test_empty_or_no_target():
    assert edit_plan._conform_overflow_beats([], 10) == []
    b = [_beat("가"*100)]
    assert edit_plan._conform_overflow_beats(b, 0) == b   # target 0 → 무변경


def test_wired_in_build_scene_first():
    import inspect
    src = inspect.getsource(edit_plan.build_scene_first_plan)
    assert "_conform_overflow_beats" in src   # 실제 배선됐는지
