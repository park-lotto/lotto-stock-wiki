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


def test_score_penalizes_recent_hook():
    # novelty 감점(belt-and-suspenders): 첫 비트(훅)가 최근 쓴 훅과 겹치면 추천점수를 깎는다.
    plan = _plan(["와 이거 진짜 대박인데요 완전 놀랐잖아요", "이거 하나면 끝이에요"], fit=5)
    base = edit_plan._score_candidate(plan)
    pen = edit_plan._score_candidate(plan, avoid_hooks=["와 이거 진짜 대박인데요 완전 놀랐잖아요"])
    assert pen < base


def test_score_no_penalty_for_fresh_hook():
    plan = _plan(["완전 새로운 신선한 오프닝 문장이에요", "이거 하나면 끝"], fit=5)
    assert edit_plan._score_candidate(plan, avoid_hooks=["전혀 다른 옛날 훅 문구"]) \
        == edit_plan._score_candidate(plan)


def test_score_penalizes_plagiarized_narration():
    # 표절 감점(2026-07-30): _plagiarism_flags가 감지하는 것과 같은 원문 베끼기를
    # 채점에도 반영한다 — 감지만 되고 점수는 안 깎이면 표절 후보가 그대로 추천된다(실사고).
    src = ["엄마가 옆에서 보더니 진짜 곱네 하시더라고요 이거 하나면 끝이더라구요"]
    copied = _plan(["엄마가 옆에서 보더니 진짜 곱네 하시더라고요 이거 하나면 끝이더라구요"], fit=5)
    original = _plan(["처음엔 반신반의했는데 써보니까 확 달라지더라고요"], fit=5)
    assert (edit_plan._score_candidate(copied, source_full_texts=src)
            < edit_plan._score_candidate(original, source_full_texts=src))


def test_score_no_plagiarism_penalty_below_threshold():
    # 짧게 겹치는 흔한 표현(임계 이하)까지 벌점 주면 정상 후보가 억울하게 깎인다.
    src = ["오늘도 화창한 날씨네요 준비물을 챙겨서 나가봅시다 즐거운 하루 되세요"]
    plan = _plan(["써보니까 확 달라지더라고요"], fit=5)
    assert (edit_plan._score_candidate(plan, source_full_texts=src)
            == edit_plan._score_candidate(plan))
