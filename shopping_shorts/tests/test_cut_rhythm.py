"""브리프 T6 — 후보 추천점수(_score_candidate)가 컷 리듬(파편화·전역 반복)을 감점한다.
T1~T5가 구성을 고쳐도 후보들이 이 축에서 다를 수 있어, 선택이 파편·반복 후보를 다시
고르지 않게 하는 안전망. 잘 구성된 후보(비트당 클립 ≤ 상한·seg 고유)는 감점 0(회귀0)."""
from shopping_shorts import edit_plan


def _beat(primary, alts=None, narr="", fit=4):
    return {"fit": fit, "forced": False, "narration": narr,
            "primary": {"seg_id": primary},
            "alternates": [{"seg_id": a} for a in (alts or [])]}


def test_cut_rhythm_penalty_zero_for_clean_composition():
    # 비트당 클립 ≤ 상한(3), seg 전부 고유 → 감점 없음(정상 경로 회귀0)
    beats = [_beat("s0"), _beat("s1"), _beat("s2")]
    assert edit_plan._cut_rhythm_penalty(beats) == 0.0


def test_cut_rhythm_penalty_flags_fragmentation():
    # 파편 클립을 몰아넣어 비트당 평균 클립이 상한을 넘음(짧은 컷 연발) → 감점 > 0
    frag = [_beat("a", ["b", "c", "d", "e", "f"]), _beat("g")]  # 7클립/2비트 = 3.5 > 3
    assert edit_plan._cut_rhythm_penalty(frag) > 0.0


def test_cut_rhythm_penalty_flags_repetition():
    # 같은 seg를 비트마다 재사용(B롤 체인 반복) → 감점 > 0
    rep = [_beat("s0", ["x"]), _beat("s0", ["x"]), _beat("s0", ["x"])]
    assert edit_plan._cut_rhythm_penalty(rep) > 0.0


def test_cut_rhythm_penalty_bounded():
    worst = [_beat("s0", ["s0", "s0", "s0", "s0", "s0", "s0"])]
    p = edit_plan._cut_rhythm_penalty(worst)
    assert 0.0 <= p <= 0.2


def test_cut_rhythm_penalty_empty():
    assert edit_plan._cut_rhythm_penalty([]) == 0.0


def test_score_demotes_fragmented_candidate():
    # 통합: 같은 fit·나레이션·seg 고유이지만 파편적인 후보가 덜 추천된다(현재는 동점 → 감점으로 강등).
    tight = {"beats": [_beat("s0", narr="예전엔 눅눅했는데 이젠 바삭해요"),
                       _beat("s1", narr="이거 하나면 끝이에요")]}
    frag = {"beats": [_beat("a", ["b", "c", "d", "e"], narr="예전엔 눅눅했는데 이젠 바삭해요"),
                      _beat("f", ["g", "h", "i"], narr="이거 하나면 끝이에요")]}
    assert edit_plan._score_candidate(tight) > edit_plan._score_candidate(frag)
