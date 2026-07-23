"""T6 — 컷리듬/반복 결정적 감점. 파편·반복 후보가 심사 순위에서 끌어내려지는지(P1·P2 재발 방어)."""
from shopping_shorts import candidate_judge


def _beat(primary_seg, alt_segs=()):
    return {"narration": "x", "primary": {"seg_id": primary_seg},
            "alternates": [{"seg_id": s} for s in alt_segs]}


def test_clean_plan_no_penalty():
    """비트당 클립 적고(≤cap) 전부 고유 → 감점 0."""
    beats = [_beat("s0"), _beat("s1"), _beat("s2", ["s3"])]
    assert candidate_judge.cut_rhythm_penalty(beats) == 0.0


def test_repetitive_plan_penalized():
    """같은 seg가 비트마다 반복 → 감점 > 0."""
    beats = [_beat("s0", ["s1", "s2"]), _beat("s0", ["s1", "s2"]), _beat("s0", ["s1", "s2"])]
    assert candidate_judge.cut_rhythm_penalty(beats) > 0.0


def test_choppy_plan_penalized():
    """비트당 클립이 상한 훨씬 초과(파편 연발) → 감점 > 0."""
    beats = [_beat("a", ["b", "c", "d", "e", "f", "g"])]  # 7컷/1비트
    assert candidate_judge.cut_rhythm_penalty(beats) > 0.0


def test_penalty_capped_at_0_3():
    """최악(전부 반복+과다 파편)이어도 상한 0.3."""
    beats = [_beat("s0", ["s0"] * 20) for _ in range(3)]
    assert candidate_judge.cut_rhythm_penalty(beats) <= 0.3


def test_empty_beats_zero():
    assert candidate_judge.cut_rhythm_penalty([]) == 0.0
    assert candidate_judge.cut_rhythm_penalty(None) == 0.0


def test_repetitive_ranks_below_clean_in_scoring():
    """두 후보가 3축 동점이어도, 반복 심한 쪽이 감점으로 최종점수가 더 낮아야."""
    clean = [_beat("s0"), _beat("s1"), _beat("s2")]
    repet = [_beat("s0", ["s1"]), _beat("s0", ["s1"]), _beat("s0", ["s1"])]
    base = 0.8
    sc_clean = round(max(0.0, base - candidate_judge.cut_rhythm_penalty(clean)), 3)
    sc_repet = round(max(0.0, base - candidate_judge.cut_rhythm_penalty(repet)), 3)
    assert sc_repet < sc_clean
