# -*- coding: utf-8 -*-
"""컷 이어붙이기(2026-09-17) — 2단계가 준 컷이 대사보다 짧으면 같은 소스 다음 컷을 이어 붙인다.

사장님: "컷이 모자랄 때 같은 영상 다음 컷을 이어 붙여라. 한 컷은 2.2초까지만 — 6초 컷 하나면 늘어진다."
근거: 조립기 assign_cuts(앞에서 길이만큼 지정)만 빈칸 0을 만들었다(자동 job ba630a537511 7→7컷).
      뒤에서 메우는 채우기는 정렬을 고쳐도 26→23컷(job 26698eb0a362)이었다.
"""
from shopping_shorts import edit_plan as ep


def _seg(vid, i, start, dur):
    return {"seg_id": f"{vid}-{i}", "video_id": vid, "start": start, "end": start + dur,
            "scene_desc": f"{vid} 장면 {i}"}


def _by_video(*segs):
    out = {}
    for s in segs:
        out.setdefault(s["video_id"], []).append(s)
    for v in out.values():
        v.sort(key=lambda s: s["start"])
    return out


def test_모자라면_같은_소스_다음_컷을_이어_붙인다():
    a0, a1, a2 = _seg("A", 0, 0.0, 1.0), _seg("A", 1, 1.0, 1.0), _seg("A", 2, 2.0, 1.0)
    bv = _by_video(a0, a1, a2)
    used = {"A-0"}
    refs = ep._extend_refs_to_narration([a0], "가" * 20, bv, used)      # 20자 ≈ 2.7초
    ids = [r["seg_id"] for r in refs]
    assert ids[0] == "A-0"
    assert ids[1:] == ["A-1", "A-2"][: len(ids) - 1], "시간순 다음 컷부터"
    assert len(ids) >= 2
    assert "A-1" in used, "붙인 컷은 used에 들어가 다른 줄이 못 가져간다"


def test_컷이_대사보다_길면_아무것도_안_붙인다():
    a0, a1 = _seg("A", 0, 0.0, 5.0), _seg("A", 1, 5.0, 1.0)
    bv = _by_video(a0, a1)
    used = {"A-0"}
    # 5초 컷의 기여는 2.2초까지만 세므로 5초라도 '충분'은 아닐 수 있다 → 짧은 대사로 시험
    refs = ep._extend_refs_to_narration([a0], "가" * 8, bv, used)         # 8자 ≈ 1.5초(최소)
    assert [r["seg_id"] for r in refs] == ["A-0"]
    assert "A-1" not in used


def test_한_컷의_기여는_2_2초까지만_센다_긴_컷_하나로_충분하다고_보지_않는다():
    """6초 컷 하나로 4초 대사를 채우면 화면 한 장이 4초 내내 멈춘다(자동조립 실측 컷당 3.5s)."""
    from shopping_shorts import config
    cap = config.MAX_SHOT_SECONDS
    a0, a1 = _seg("A", 0, 0.0, 6.0), _seg("A", 1, 6.0, 6.0)
    bv = _by_video(a0, a1)
    used = {"A-0"}
    refs = ep._extend_refs_to_narration([a0], "가" * 30, bv, used)        # 30자 ≈ 4초 > cap
    assert [r["seg_id"] for r in refs] == ["A-0", "A-1"], "cap(%.1f) 넘는 대사면 컷을 더 붙인다" % cap


def test_다른_소스나_이미_쓴_컷이나_앞_컷은_안_가져온다():
    a0 = _seg("A", 0, 3.0, 1.0)
    a_before = _seg("A", 9, 0.0, 1.0)          # 앞 컷(시간 역행)
    a_used = _seg("A", 1, 4.0, 1.0)            # 다음 줄이 이미 지정한 컷
    b0 = _seg("B", 0, 4.0, 1.0)                # 다른 소스
    bv = _by_video(a0, a_before, a_used, b0)
    used = {"A-0", "A-1"}
    refs = ep._extend_refs_to_narration([a0], "가" * 20, bv, used)
    assert [r["seg_id"] for r in refs] == ["A-0"], "붙일 게 없으면 그만둔다(폴백 없음 — 채우기가 받는다)"


def test_짧은_조각은_건너뛴다():
    a0 = _seg("A", 0, 0.0, 1.0)
    tiny = _seg("A", 1, 1.0, 0.5)              # < _MIN_CUT_SECONDS — 렌더가 흡수해 안 보임
    a2 = _seg("A", 2, 1.5, 2.0)
    bv = _by_video(a0, tiny, a2)
    used = {"A-0"}
    refs = ep._extend_refs_to_narration([a0], "가" * 20, bv, used)
    assert "A-1" not in [r["seg_id"] for r in refs]
    assert "A-2" in [r["seg_id"] for r in refs]


def test_build_inherit_plan에_배선돼_있다():
    import inspect
    src = inspect.getsource(ep.build_inherit_plan)
    assert "_extend_refs_to_narration(" in src
