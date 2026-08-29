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
    plan = _plan_phrase_clips(_beat(), SEGS, 3.86)
    assert plan and len(plan) == 3
    durs = [c["out_dur"] for c in plan]
    # 컷1 = 리드인 0.29 + 구절1 1.1 / 컷2 = 구절2 0.68 / 컷3 = 구절3 + 꼬리(합계 보전)
    assert durs[0] == pytest.approx(0.29 + 1.1, abs=1e-6)
    assert durs[1] == pytest.approx(0.68, abs=1e-6)
    assert sum(durs) == pytest.approx(3.86, abs=1e-6)


def test_fewer_materials_last_covers_rest():
    plan = _plan_phrase_clips(_beat(), SEGS[:2], 3.86)
    assert len(plan) == 2
    assert plan[1]["out_dur"] == pytest.approx(3.86 - (0.29 + 1.1), abs=1e-6)


def test_no_timetable_falls_back_none():
    assert _plan_phrase_clips(_beat(narration=""), SEGS, 3.86) is None
    assert _plan_phrase_clips(_beat(), [], 3.86) is None
