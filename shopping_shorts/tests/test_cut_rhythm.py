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
    # 긴 대사도 첫 조각의 소스 하나로 비트 끝까지 이어 튼다(main 30d0c5ed2, job 956a 정지 재현·tools/check_cut_rhythm_hold.py).
    #   회사 09-22 트랙(370508332)의 "5초 홀드 + 두 번째 컷"은 조각이 하나뿐이면 5초 뒤 정지가 재발해 병합 때 접었다(09-23).
    long = va.plan_beat_clips_for(beat, tts_dur=9.0, src_durs={"v1": 30.0, "v2": 30.0, "v3": 30.0})
    assert all(c["video_id"] == "v1" for c in long)
    assert abs(sum(c["out_dur"] for c in long) - 9.0) < 0.05
    assert sum(c.get("src_dur", 0) for c in long) > 8.5      # 실프레임으로 채운다(정지·늘리기 없음)


def test_hold_아니면_조각을_한번씩_비례로_쓴다():
    beat = _beat(1, _seg("v1", 0.0, 3.0), [_seg("v2", 0.0, 3.0), _seg("v3", 0.0, 3.0)],
                 cut_rhythm={"max_shot": 4.0, "hold": False})
    plan = va.plan_beat_clips_for(beat, tts_dur=6.0, src_durs={"v1": 30.0, "v2": 30.0, "v3": 30.0})
    # 리듬 칸(홀드 아님) = 고른 조각을 한 번씩·순서대로, 시간은 비례로. 같은 조각으로 되돌아오지 않는다(중복 장면의 뿌리).
    assert [c["video_id"] for c in plan] == ["v1", "v2", "v3"]
    assert all(abs(c["out_dur"] - 2.0) < 1e-6 for c in plan)


class _Store:
    def __init__(self, v): self.v = v
    def get_setting(self, k, d=""): return self.v if k == "cut_rhythm_enabled" else d


def test_스위치_admin은_관리자_job에만_표식을_단다():
    plan = {"beats": [{"beat_idx": 0, "narration": "출산맘들 환장하게 만든 발명품"},
                      {"beat_idx": 1, "role": "고조1",
                       "narration": "손에 묻히던 기존 방식과는 달리 두피에만 쏙 스며들게 해 준다는 거"},
                      {"beat_idx": 2, "narration": "바쁜 아침에 앰플을 덜어내다가"}]}
    assert mp._apply_cut_rhythm(plan, _Store("admin"), {"customer_id": 0}) == 3
    cr = [b["cut_rhythm"]["hold"] for b in plan["beats"]]
    assert cr == [True, True, False]           # 훅 · 핵심 결과 줄만 hold
    plan2 = {"beats": [{"beat_idx": 0, "narration": "x"}]}
    assert mp._apply_cut_rhythm(plan2, _Store("admin"), {"customer_id": 57}) == 0
    assert "cut_rhythm" not in plan2["beats"][0]
    assert mp._apply_cut_rhythm(plan2, _Store(""), {"customer_id": 0}) == 0


def test_편성단계_조각줄이기_홀드는_primary만_나머지는_2개():
    plan = {"beats": [
        {"beat_idx": 0, "narration": "훅", "primary": _seg("v1", 0, 1), "alternates": [_seg("v2", 0, 1), _seg("v3", 0, 1)]},
        {"beat_idx": 1, "role": "고조1", "narration": "…없애 버렸다는 거", "primary": _seg("v1", 2, 3), "alternates": [_seg("v2", 2, 3)]},
        {"beat_idx": 2, "narration": "바쁜 아침에 덜어내다가", "primary": _seg("v1", 4, 5), "alternates": [_seg("v2", 4, 5), _seg("v3", 4, 5), _seg("v4", 4, 5)]},
    ]}
    plan["beats"][2]["target_seconds"] = 9.0          # 9초 줄 → 4컷(예비 3개, 상한 4)
    assert mp._trim_for_cut_rhythm(plan) == 3
    assert [len(b["alternates"]) for b in plan["beats"]] == [0, 0, 3]
    assert [b["cut_rhythm"]["hold"] for b in plan["beats"]] == [True, True, False]


def test_홀드는_훅_고조1결과줄_반전만():
    plan = {"beats": [
        {"beat_idx": 0, "role": "훅", "narration": "훅", "primary": _seg("v1", 0, 1)},
        {"beat_idx": 1, "role": "고조1", "narration": "요철로 먼지를 없애 버렸다는 거", "primary": _seg("v1", 2, 3)},
        {"beat_idx": 2, "role": "고조2", "narration": "청소포 낭비까지 없애 버렸다는 거", "primary": _seg("v1", 4, 5)},
        {"beat_idx": 3, "role": "반전", "narration": "물에 씻어 계속 쓴다는 거", "primary": _seg("v1", 6, 7)},
    ]}
    mp._trim_for_cut_rhythm(plan)
    assert [b["cut_rhythm"]["hold"] for b in plan["beats"]] == [True, True, False, True]


def test_줄안_컷은_낱말경계에_붙는다():
    narr = "일반 걸레로 닦다 보면 먼지가 밀리기만 해서 다시 닦아야 했던 그 지옥을"
    plan = [{"video_id": "v1", "start": 0, "src_dur": 2.0, "out_dur": 2.0}, {"video_id": "v2", "start": 0, "src_dur": 2.0, "out_dur": 2.0},
            {"video_id": "v3", "start": 0, "src_dur": 2.0, "out_dur": 2.0}]
    va._snap_cuts_to_words(plan, narr, 6.0)
    wb = va._word_boundaries(narr, 6.0)
    t = 0.0
    for c in plan[:-1]:
        t += c["out_dur"]
        assert min(abs(w - t) for w in wb) < 0.02          # 경계가 낱말 사이에 정확히 붙었다
    assert abs(sum(c["out_dur"] for c in plan) - 6.0) < 1e-6
