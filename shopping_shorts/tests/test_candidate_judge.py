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


# ── rank(): 비교 채점(동점 해소, 2026-08-09) ──────────────────────────────

_BEATS2 = [{"narration": "업체 부르면 얼마게요", "primary": {"scene_desc": "곰팡이 벽"}},
           {"narration": "이렇게 하면 끝입니다", "primary": {"scene_desc": "시공 완료"}}]


def test_rank_parses_scores_and_ranks():
    def _call(prompt, schema):
        return {"ranking": [{"candidate": 1, "score": 80, "reason": "훅 강함"},
                            {"candidate": 2, "score": 60, "reason": "무난"}]}
    r = candidate_judge.rank([_BEATS, _BEATS2], call=_call)
    assert r[0]["score"] == 0.8 and r[0]["rank"] == 1 and r[0]["reason"] == "훅 강함"
    assert r[1]["score"] == 0.6 and r[1]["rank"] == 2


def test_rank_prompt_compares_all_and_forbids_ties():
    seen = {}
    def _call(prompt, schema):
        seen["p"] = prompt
        return {"ranking": [{"candidate": 1, "score": 70}, {"candidate": 2, "score": 50}]}
    candidate_judge.rank([_BEATS, _BEATS2], call=_call)
    assert "[후보 1]" in seen["p"] and "[후보 2]" in seen["p"]
    assert "동점 금지" in seen["p"]


def test_rank_none_on_partial_or_failure():
    # 후보 2개인데 1개만 채점 → 빠진 쪽이 보정을 못 받아 왜곡 → 전체 무효
    assert candidate_judge.rank(
        [_BEATS, _BEATS2],
        call=lambda p, s: {"ranking": [{"candidate": 1, "score": 70}]}) is None
    assert candidate_judge.rank([_BEATS, _BEATS2], call=lambda p, s: None) is None
    assert candidate_judge.rank([_BEATS], call=lambda p, s: {}) is None      # 후보 1개
    def _boom(p, s):
        raise RuntimeError("x")
    assert candidate_judge.rank([_BEATS, _BEATS2], call=_boom) is None


def test_rank_clamps_and_ignores_bad_rows():
    def _call(prompt, schema):
        return {"ranking": [{"candidate": 1, "score": 999}, "쓰레기",
                            {"candidate": 2, "score": -5}]}
    r = candidate_judge.rank([_BEATS, _BEATS2], call=_call)
    assert r[0]["score"] == 1.0 and r[1]["score"] == 0.0


def test_apply_judge_rank_breaks_ties_and_falls_back():
    """동점 3후보가 rank 보정으로 갈리고, rank 실패면 score 무변경(회귀 0)."""
    from shopping_shorts import edit_plan
    def _mk():
        return [{"plan": {"beats": _BEATS}, "score": 0.467},
                {"plan": {"beats": _BEATS2}, "score": 0.467},
                {"plan": {"beats": _BEATS}, "score": 0.467}]
    def _call(prompt, schema):
        return {"ranking": [{"candidate": 1, "score": 80}, {"candidate": 2, "score": 60},
                            {"candidate": 3, "score": 40}]}
    cands = _mk()
    edit_plan._apply_judge_rank(cands, True, _call)
    assert [c["score"] for c in cands] == [0.497, 0.477, 0.457]      # ±0.05 안 보정
    assert cands[0]["judge_cmp"]["rank"] == 1
    for judge_on, call in ((False, _call), (True, lambda p, s: None)):
        cands = _mk()
        edit_plan._apply_judge_rank(cands, judge_on, call)
        assert [c["score"] for c in cands] == [0.467, 0.467, 0.467]
        assert all("judge_cmp" not in c for c in cands)


def test_rank_wired_into_both_pick_paths():
    """배선 잠금(style_penalty 잠금과 같은 함정 회피): _apply_judge_rank 호출이
    1소스·scene_first 두 경로에 다 있어야 한다 — 한쪽만 지워져도 동점이 재발한다."""
    import inspect
    from shopping_shorts import edit_plan
    src = inspect.getsource(edit_plan)
    assert src.count("_apply_judge_rank(cands, judge") >= 2
