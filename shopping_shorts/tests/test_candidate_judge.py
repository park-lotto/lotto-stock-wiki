"""후보 심사위원 — 대본품질·장면싱크·스토리라인 3축 채점(사장님 기준)."""
from shopping_shorts import candidate_judge


_BEATS = [{"narration": "이거 왜 이제 알았지", "primary": {"scene_desc": "바나나 써는", "action": "자르다"}},
          {"narration": "짜잔 완성", "primary": {"scene_desc": "완성 접시", "action": "올리다"}}]


def test_judge_parses_and_totals():
    def _call(prompt, schema):
        return {"script_quality": 5, "scene_sync": 4, "storyline": 3, "reason": "좋음"}
    r = candidate_judge.judge(_BEATS, call=_call)
    assert (r["script_quality"], r["scene_sync"], r["storyline"]) == (5, 4, 3)
    assert r["total"] == round(12 / 15.0, 3)      # (5+4+3)/15
    assert r["reason"] == "좋음"


def test_judge_clamps_out_of_range():
    def _call(prompt, schema):
        return {"script_quality": 9, "scene_sync": -2, "storyline": "x"}
    r = candidate_judge.judge(_BEATS, call=_call)
    assert r["script_quality"] == 5 and r["scene_sync"] == 0 and r["storyline"] == 0


def test_judge_prompt_has_three_axes():
    seen = {}
    def _call(prompt, schema):
        seen["p"] = prompt
        return {"script_quality": 3, "scene_sync": 3, "storyline": 3}
    candidate_judge.judge(_BEATS, call=_call)
    for kw in ("script_quality", "scene_sync", "storyline", "설명체", "이야기"):
        assert kw in seen["p"]


def test_judge_none_on_failure_or_empty():
    assert candidate_judge.judge([], call=lambda p, s: {"a": 1}) is None
    assert candidate_judge.judge(_BEATS, call=lambda p, s: None) is None
