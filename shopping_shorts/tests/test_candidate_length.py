"""후보 길이 적합(2026-07-25 세션#2) — 선택 점수가 길이를 무시해 21.3초짜리가 30초 목표에
뽑히던 것(사장님 제보: 후보 A/B/C 길이 뒤죽박죽). _score_candidate에 길이감점을 넣어
목표초에서 벗어난 후보를 강등한다. 순수 계산(Gemini 없음)."""
from shopping_shorts import edit_plan


def _beat(sid, tsec, narr="맛있게 구워서 진짜 놀랐어요"):
    return {"fit": 5, "primary": {"seg_id": sid}, "alternates": [],
            "narration": narr, "target_seconds": tsec, "role": "body"}


def test_length_penalty_zero_at_target():
    beats = [_beat(f"s0-{i}", 6.0) for i in range(5)]     # 합 30s = 목표
    assert edit_plan._length_penalty(beats, 30) == 0.0


def test_length_penalty_zero_for_slight_over():
    beats = [_beat(f"s0-{i}", 6.6) for i in range(5)]     # 33s = 1.1배(conform 흡수 대역)
    assert edit_plan._length_penalty(beats, 30) == 0.0


def test_length_penalty_positive_when_short():
    beats = [_beat(f"s0-{i}", 4.26) for i in range(5)]    # 21.3s = job 실측
    assert edit_plan._length_penalty(beats, 30) > 0.1


def test_length_penalty_zero_without_target():
    beats = [_beat(f"s0-{i}", 4.26) for i in range(5)]
    assert edit_plan._length_penalty(beats, None) == 0.0  # 목표 없으면 기존 동작(무감점)


def test_score_prefers_target_length():
    on_target = {"beats": [_beat(f"a{i}", 6.0) for i in range(5)]}    # 30s
    too_short = {"beats": [_beat(f"b{i}", 4.26) for i in range(5)]}   # 21.3s (품질·fit 동일)
    assert (edit_plan._score_candidate(too_short, target_seconds=30)
            < edit_plan._score_candidate(on_target, target_seconds=30))


def test_score_backward_compat_no_target():
    # target_seconds 미전달 시 길이감점 없이 기존과 동일 점수(회귀 방지)
    p = {"beats": [_beat(f"c{i}", 4.26) for i in range(5)]}
    assert edit_plan._score_candidate(p) == edit_plan._score_candidate(p, target_seconds=None)
