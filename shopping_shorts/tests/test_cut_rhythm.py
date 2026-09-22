# -*- coding: utf-8 -*-
"""컷 리듬(2026-09-22) — 관리자 스위치 뒤. 히트작 실측(컷 중앙 1.9초·핵심 줄 3~6초 홀드)을 따른다."""
from shopping_shorts import video_assemble as va
from shopping_shorts import mix_pipeline as mp


def _seg(vid, start, end):
    return {"video_id": vid, "start": start, "end": end, "seg_id": f"{vid}:{start}"}


def _beat(idx, prim, alts=None, **kw):
    b = {"beat_idx": idx, "primary": prim}
    if alts:
        b["alternates"] = alts
    b.update(kw)
    return b


def test_표식_없으면_종전_라운드로빈_그대로():
    beat = _beat(1, _seg("v1", 0.0, 2.0), [_seg("v2", 0.0, 2.0), _seg("v3", 0.0, 2.0)])
    plan = va.plan_beat_clips_for(beat, tts_dur=6.0, src_durs={"v1": 30.0, "v2": 30.0, "v3": 30.0})
    assert len(plan) >= 3 and all(c["out_dur"] <= 2.2 + 1e-6 for c in plan)


def test_hold는_첫_조각_하나로_문장_전체를_이어_튼다():
    beat = _beat(1, _seg("v1", 0.0, 1.5), [_seg("v2", 0.0, 2.0), _seg("v3", 0.0, 2.0)],
                 cut_rhythm={"max_shot": 4.0, "hold": True})
    plan = va.plan_beat_clips_for(beat, tts_dur=4.5, src_durs={"v1": 30.0, "v2": 30.0, "v3": 30.0})
    assert len(plan) == 1 and plan[0]["video_id"] == "v1"
    assert abs(sum(c["out_dur"] for c in plan) - 4.5) < 0.05
    assert plan[0]["src_dur"] >= 4.0        # 조각(1.5초)을 넘어 원본을 실프레임으로 이어 튼다


def test_hold_아니면_상한_4초로_컷이_줄어든다():
    beat = _beat(1, _seg("v1", 0.0, 3.0), [_seg("v2", 0.0, 3.0), _seg("v3", 0.0, 3.0)],
                 cut_rhythm={"max_shot": 4.0, "hold": False})
    plan = va.plan_beat_clips_for(beat, tts_dur=6.0, src_durs={"v1": 30.0, "v2": 30.0, "v3": 30.0})
    assert len(plan) <= 2 and all(c["out_dur"] <= 4.0 + 1e-6 for c in plan)


class _Store:
    def __init__(self, v): self.v = v
    def get_setting(self, k, d=""): return self.v if k == "cut_rhythm_enabled" else d


def test_스위치_admin은_관리자_job에만_표식을_단다():
    plan = {"beats": [{"beat_idx": 0, "narration": "출산맘들 환장하게 만든 발명품"},
                      {"beat_idx": 1, "narration": "손에 묻히던 기존 방식과는 달리 두피에만 쏙 스며들게 해 준다는 거"},
                      {"beat_idx": 2, "narration": "바쁜 아침에 앰플을 덜어내다가"}]}
    assert mp._apply_cut_rhythm(plan, _Store("admin"), {"customer_id": 0}) == 3
    cr = [b["cut_rhythm"]["hold"] for b in plan["beats"]]
    assert cr == [True, True, False]           # 훅 · 핵심 결과 줄만 hold
    plan2 = {"beats": [{"beat_idx": 0, "narration": "x"}]}
    assert mp._apply_cut_rhythm(plan2, _Store("admin"), {"customer_id": 57}) == 0
    assert "cut_rhythm" not in plan2["beats"][0]
    assert mp._apply_cut_rhythm(plan2, _Store(""), {"customer_id": 0}) == 0
