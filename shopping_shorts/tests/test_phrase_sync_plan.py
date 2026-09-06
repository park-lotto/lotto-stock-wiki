# -*- coding: utf-8 -*-
"""구절 맞춤(2026-08-29 사장님 "개수+길이까지 1:1") — 컷 경계 = 자막 구절 경계.

화면(scene_play.js planClips phraseSync 분기)과 짝인 서버판(_plan_phrase_clips).
컷1이 리드인을 얹고 마지막 컷이 꼬리를 얹어 합계 = tts_dur. 재료가 구절보다 적으면
마지막 재료가 남은 구절을 이어 커버한다. 시간표를 못 만들면 None(종전 배분 폴백).
"""
import pytest

from shopping_shorts.video_assemble import _plan_phrase_clips

SEGS = [{"video_id": "s0", "start": 1.0}, {"video_id": "s1", "start": 5.0},
        {"video_id": "s0", "start": 9.0}]


def _beat(**kw):
    b = {"narration": "저 친구네 집 갔다가 충격 받았어요. 애들 아침으로 이걸 해주더라고요",
         "caption_lines": ["저 친구네 집 갔다가", "충격 받았어요", "애들 아침으로 이걸 해주더라고요"],
         "cap_durs": [1.1, 0.68, 1.79], "cap_lead": 0.29}
    b.update(kw)
    return b


def test_cut_bounds_equal_phrase_bounds():
    """★2026-09-06 개정 — 컷 개수는 이제 **칸 길이**가 정한다(cuts_for_beat).

    종전 단언은 "컷 수 = 구절 수"(여기선 3개)였다. 그런데 그 규칙이 화면을 잘게
    썰어 컷의 71%가 1초 미만이 됐고("정신없다" — 사장님), 2초 이상 칸은 2컷으로
    묶기로 했다. 3.86초 칸이므로 **2컷**이 맞고, 경계는 여전히 **구절 경계 위**에서
    고른다(등분 지점에 가장 가까운 자리). 합계 보존은 그대로다.
    """
    plan = _plan_phrase_clips(_beat(), SEGS, 3.86)
    assert plan and len(plan) == 2, "3.86초 칸은 2컷(2초 이상 규칙)"
    durs = [c["out_dur"] for c in plan]
    # 경계 후보 [0, 1.39, 2.07, 3.86] 중 등분점 1.93에 가장 가까운 2.07을 고른다
    assert durs[0] == pytest.approx(0.29 + 1.1 + 0.68, abs=1e-6)
    assert sum(durs) == pytest.approx(3.86, abs=1e-6)
    # 컷이 줄어도 1초 미만이 안 생긴다(이 변경의 목적)
    assert min(durs) >= 1.0


def test_재료가_적으면_담은_순서대로_돌아간다():
    """2026-09-02 사장님: "장면을 빼면 두 개가 없어지고 넣으면 갑자기 배치가 바뀐다."

    종전 규칙(마지막 컷이 남은 구절을 통째로 덮음 → 뒤에 화면 전환 없음, 그 뒤엔
    '뒤가 남은 조각을 골라 쓰기')은 자리↔조각 관계가 재료 개수·잔량에 따라 달라져
    조각 하나를 빼면 뒤 배치가 통째로 밀렸다. 이제는 k % 재료수로 **정해진다**.
    """
    plan = _plan_phrase_clips(_beat(), SEGS[:2], 3.86)
    # ★2026-09-06 개정: 컷 수는 구절 수가 아니라 **칸 길이**가 정한다(3.86초 → 2컷).
    #   이 테스트의 요지는 개수가 아니라 **재료가 담은 순서대로 돈다**는 것이므로
    #   그 단언은 그대로 지킨다(마지막 컷이 남은 구절을 통째로 덮지 않는다).
    assert len(plan) == 2, "3.86초 칸은 2컷"
    vids = [c["video_id"] for c in plan]
    assert vids == [SEGS[0]["video_id"], SEGS[1]["video_id"]], vids
    assert sum(c["out_dur"] for c in plan) == pytest.approx(3.86, abs=1e-6)


def test_조각을_빼도_앞자리는_그대로다():
    """이게 제보의 핵심이다 — 하나 뺐는데 둘이 사라진 것처럼 보이던 것."""
    full = _plan_phrase_clips(_beat(), SEGS, 3.86)
    less = _plan_phrase_clips(_beat(), SEGS[:2], 3.86)
    assert full[0]["video_id"] == less[0]["video_id"]
    assert full[1]["video_id"] == less[1]["video_id"]
    assert len(full) == len(less), "칸 수(=구절 수)는 재료 개수와 무관하게 유지된다"


def test_no_timetable_falls_back_none():
    assert _plan_phrase_clips(_beat(narration=""), SEGS, 3.86) is None
    assert _plan_phrase_clips(_beat(), [], 3.86) is None
