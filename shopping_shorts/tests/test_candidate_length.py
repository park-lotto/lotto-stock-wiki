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


# ── 칸별 길이(2026-08-27 사장님 "한 컷당 너무 길게 나올 때가 많다") ──────────
# 총 길이만 보던 _length_penalty는 30초를 3칸에 몰아넣은 후보(칸당 10초)와 12칸에 고르게
# 나눈 후보를 **같은 점수**로 봤다. 실측: 화면에 6.7초·10.4초짜리 칸이 떴다.
# 기준은 사장님이 준 문장 "여러분 다이소 가시면 이건 꼭 사야 해요"(16자·2.2초).
_LONG = ("얼마 전 옷장 정리하던 언니가 남편이 즐겨 입는 티셔츠 목이 다 늘어나서 "
         "속상해하길래 제가 살짝 챙겨둔 툴을 알려줬거든요.")
_SHORT = "여러분 다이소 가시면 이건 꼭 사야 해요"


def test_beat_length_penalty_zero_for_short_beats():
    """사장님 기준 길이면 감점 0 — 정상 대본이 억울하게 강등되면 안 된다(회귀 0)."""
    beats = [_beat(f"s{i}", 2.2, _SHORT) for i in range(5)]
    assert edit_plan._beat_length_penalty(beats) == 0.0


def test_beat_length_penalty_hits_long_beats():
    """한 칸에 사연을 몰아넣은 후보는 감점된다."""
    beats = [_beat("s0", 6.7, _LONG), _beat("s1", 6.7, _LONG)]
    assert edit_plan._beat_length_penalty(beats) > 0.0


def test_beat_length_penalty_is_wired_into_score(monkeypatch):
    """★감점이 _score_candidate에 **실제로 배선**됐나(호출부 확인).

    ⚠️순위가 뒤집히는지로 검증하지 않는다 — 실측(2026-08-27)에서 같은 총 길이일 때
      긴 칸 후보 0.753 vs 짧은 칸 후보 0.750으로 **긴 쪽이 이겼다**. 이유는 품질 채점
      (_candidate_quality)이 긴 문장에 0.33을 주고 사장님이 원한 짧은 문장
      "여러분 다이소 가시면 이건 꼭 사야 해요"에는 **0점**을 줬기 때문이다.
      상한을 0.15로 올리면 뒤집히지만 그러면 "전부 짧으면 늘리는" 장치가 무력해진다
      (test_scene_first_lengthen 2건). 즉 이 감점은 동점 부근을 갈라주는 보조이고,
      칸을 짧게 만드는 본체는 프롬프트다. 여기서는 배선만 못 박는다.
      ⏭ 품질 채점이 짧은 문장에 0점을 주는 문제는 별건으로 다뤄야 한다.
    """
    beats = [_beat(f"L{i}", 6.7, _LONG) for i in range(4)]
    seen = {}

    def spy(bs, target_seconds=None, **kw):
        seen["called"] = True
        return 0.5                                   # 크게 깎아 반영 여부를 눈에 보이게

    base = edit_plan._score_candidate({"beats": beats})
    monkeypatch.setattr(edit_plan, "_beat_length_penalty", spy)
    after = edit_plan._score_candidate({"beats": beats})
    assert seen.get("called"), "_score_candidate가 칸 길이 감점을 부르지 않는다"
    assert after < base, "감점이 점수에 반영되지 않는다"


def test_beat_length_penalty_is_capped_below_total_length():
    """★상한은 총 길이 감점(0.3)보다 **낮아야** 한다.

    같게 두면 "너무 짧은 후보를 늘리는 장치"(_lengthen 재생성)가 무력해진다 — 늘린 긴
    후보를 이 감점이 도로 깎아 총 2초짜리가 추천으로 뽑혔다(2026-08-27 실측).
    대본이 목표보다 짧은 것이 칸이 긴 것보다 나쁘다.
    """
    beats = [_beat("s0", 20.0, _LONG * 5)]
    assert edit_plan._beat_length_penalty(beats) <= 0.10, (
        "0.15면 test_scene_first_lengthen 2건이 깨진다 — 실측으로 확인한 경계다")


def test_beat_length_penalty_survives_junk_input():
    """빈 값·이상한 모양이 와도 터지지 않는다(채점이 죽으면 대본이 통째로 못 나온다)."""
    assert edit_plan._beat_length_penalty([]) == 0.0
    assert edit_plan._beat_length_penalty(None) == 0.0
    assert edit_plan._beat_length_penalty([None, "문자열", {"narration": None}]) == 0.0
