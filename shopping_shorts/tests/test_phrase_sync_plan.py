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
    """컷 경계 = 자막 구절 경계. **3구절이면 3컷**이다.

    ★2026-09-06: 하루 사이 "칸 길이가 컷 개수를 정한다"·"짧은 칸은 합친다"를 넣었다가
      **둘 다 되돌렸다** — 담은 장면이 화면에 안 나와 사장님이 라이브 편집을 못 하셨다.
      컷 개수를 손대는 규칙은 넣지 마라. 짧은 컷이 거슬리면 자막 줄을 합치는 쪽으로
      풀어야 한다(그건 사장님이 화면에서 직접 하신다).
    """
    plan = _plan_phrase_clips(_beat(), SEGS, 3.86)
    assert plan and len(plan) == 3, "3구절이면 3컷"
    durs = [c["out_dur"] for c in plan]
    # 컷1 = 리드인 0.29 + 구절1 1.1 / 컷2 = 구절2 0.68 / 컷3 = 구절3 + 꼬리
    assert durs[0] == pytest.approx(0.29 + 1.1, abs=1e-6)
    assert durs[1] == pytest.approx(0.68, abs=1e-6)
    assert sum(durs) == pytest.approx(3.86, abs=1e-6)


def test_재료가_적으면_이어붙인다():
    """2026-09-11 사장님: "줄을 4칸으로 바꾸면 장면은 2개인데 줄만 4개면 편하잖아."

    09-02엔 k % 재료수로 **순환**(1,2,1,2)시켰다 — 조각 하나를 빼도 앞자리가 안 밀리게.
    그런데 고객 실측(job 6534d20ee935): 자막을 4줄로 쪼개자 조각 2개가 1,2,1,2로 돌아
    같은 장면이 두 번(앞 것 0.57초) 나왔고 고객은 오류로 봤다.
    이제는 **이어붙임**(1,1,2,2): 조각 k가 자기 몫의 구절을 연달아 덮는다 → 화면상 컷은
    조각 수 그대로, 자막만 늘어난다. 자리는 여전히 k·개수만으로 정해진다(예측 가능).
    ★화면(scene_play.js planClips)과 같은 식 — 한쪽만 고치면 미리보기와 결과물이 어긋난다.
    """
    plan = _plan_phrase_clips(_beat(), SEGS[:2], 3.86)
    assert len(plan) == 3, "구절 수만큼 항목은 만들어진다(경계 = 자막 구절)"
    vids = [c["video_id"] for c in plan]
    assert vids == [SEGS[0]["video_id"], SEGS[0]["video_id"], SEGS[1]["video_id"]], vids
    # 같은 조각이 이어질 땐 **이어서** 재생한다(처음부터 다시가 아니라) — 화면상 한 컷
    assert plan[1]["start"] == pytest.approx(plan[0]["start"] + plan[0]["out_dur"], abs=1e-6)
    assert sum(c["out_dur"] for c in plan) == pytest.approx(3.86, abs=1e-6)


def test_조각2_구절4는_1122():
    """고객 사고 그 모양 그대로 — 조각 2개에 자막 4줄이면 1,1,2,2 (같은 장면이 흩어져 두 번 안 나온다)."""
    b = _beat(narration="옷장은 좁고 옷이랑 이불 정리 해야되서 고민이었는데",
              caption_lines=["옷장은 좁고", "옷이랑 이불", "정리 해야되서", "고민이었는데"],
              cap_durs=[0.72, 0.57, 0.52, 0.77], cap_lead=0.087)
    plan = _plan_phrase_clips(b, SEGS[:2], 2.9)
    vids = [c["video_id"] for c in plan]
    assert vids == ["s0", "s0", "s1", "s1"], vids


def test_조각을_빼도_앞자리는_그대로다():
    """이게 제보의 핵심이다 — 하나 뺐는데 둘이 사라진 것처럼 보이던 것."""
    full = _plan_phrase_clips(_beat(), SEGS, 3.86)
    less = _plan_phrase_clips(_beat(), SEGS[:2], 3.86)
    assert full[0]["video_id"] == less[0]["video_id"], "첫 자리는 조각을 빼도 그대로"
    assert len(full) == len(less), "칸 수(=구절 수)는 재료 개수와 무관하게 유지된다"
    # 이어붙임(09-11): 빠진 조각의 자리는 앞 조각이 **이어서** 덮는다 — 흩어져 두 번 나오지 않는다.
    order = [c["video_id"] for c in less]
    seen, prev = [], None
    for v in order:
        if v != prev:
            assert v not in seen, f"같은 조각이 흩어져 다시 나왔다: {order}"
            seen.append(v)
        prev = v


def test_no_timetable_falls_back_none():
    assert _plan_phrase_clips(_beat(narration=""), SEGS, 3.86) is None
    assert _plan_phrase_clips(_beat(), [], 3.86) is None
