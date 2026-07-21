"""P1 품질게이트 — scene_first 추천점수가 매칭(fit)뿐 아니라 대화체(tone)·재미강도(fun)도 본다.
같은 fit이라도 '말투 자연스럽고 재미장치 있는' 후보가 추천되게(추천안=최고 품질)."""
from shopping_shorts import edit_plan


def _plan(narrs, fit=4):
    beats = [{"fit": fit, "forced": False, "narration": n,
              "primary": {"seg_id": f"s{i}"}, "alternates": []}
             for i, n in enumerate(narrs)]
    return {"beats": beats}


def test_quality_lifts_fun_conversational_over_flat():
    # 둘 다 fit·forced·diversity 동일 — 차이는 대본 품질뿐.
    fun = _plan(["예전엔 눅눅했는데 이젠 진짜 바삭해졌어요",
                 "이거 하나면 끝나더라구요"])
    flat = _plan(["확인하셨어요", "확인하셨어요"])   # AI냄새·문어체·어미단조
    assert edit_plan._score_candidate(fun) > edit_plan._score_candidate(flat)


def test_quality_does_not_break_empty_and_fit_ranking():
    # 기존 계약 회귀: 빈 beats=0.0, 고fit>저fit 유지
    assert edit_plan._score_candidate({"beats": []}) == 0.0
    good = _plan(["예전엔 별로였는데 이젠 최고예요"], fit=5)
    bad = {"beats": [{"fit": 1, "forced": True, "narration": "음",
                      "primary": {"seg_id": "a"}, "alternates": []}]}
    assert edit_plan._score_candidate(good) > edit_plan._score_candidate(bad)


def test_score_bounded_0_1():
    s = edit_plan._score_candidate(_plan(["예전엔 눅눅했는데 이젠 바삭해요"], fit=5))
    assert 0.0 <= s <= 1.0
