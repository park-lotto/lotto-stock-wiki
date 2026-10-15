# -*- coding: utf-8 -*-
"""컷 이어붙이기(09-17) → 관제 084에서 ai_match.ensure_cover 한 곳으로 합침. 옛 정책이 그대로 지켜지는지 본다."""
import inspect

from shopping_shorts import ai_match as am, edit_plan as ep


def _idx(*rows):
    return {sid: {"secs": secs, "vid": sid.rsplit("-", 1)[0], "label": lab, "kind": "", "outro": False} for sid, secs, lab in rows}


def test_build_inherit_plan에_배선돼_있다():
    src = inspect.getsource(ep.build_inherit_plan)
    assert "ensure_cover(" in src and not hasattr(ep, "_extend_refs_to_narration")


def test_짧은_컷은_뒤로_밀되_막지_않는다():
    idx = _idx(("A-0", 1.0, "x"), ("A-1", 1.0, "y"), ("A-2", 2.0, "z"))
    bs = [{"segs": ["A-0"]}]
    am.ensure_cover(bs, [{"text": "가" * 12}], idx, None)
    assert bs[0]["segs"][1] == "A-2", bs                 # 1.2초 이상 컷 먼저
    idx2 = _idx(("A-0", 1.0, "x"), ("A-1", 1.0, "y"))
    bs2 = [{"segs": ["A-0"]}]
    am.ensure_cover(bs2, [{"text": "가" * 12}], idx2, None)
    assert bs2[0]["segs"] == ["A-0", "A-1"]              # 긴 컷이 없으면 짧은 컷이라도


def test_한_컷_기여는_2점2초까지():
    idx = _idx(("A-0", 6.0, "x"), ("A-1", 1.5, "y"))
    bs = [{"segs": ["A-0"]}]
    am.ensure_cover(bs, [{"text": "가" * 22}], idx, None)   # 약 3.8초 → 6초 한 컷은 2.2초로만 셈 → 한 장면 더
    assert bs[0]["segs"] == ["A-0", "A-1"]


def test_다음_컷이_쓰였으면_더_뒤를_잇는다():
    idx = _idx(("A-0", 1.0, "x"), ("A-1", 1.5, "y"), ("A-2", 1.5, "z"))
    bs = [{"segs": ["A-0"]}, {"segs": ["A-1"]}]
    am.ensure_cover(bs, [{"text": "가" * 14}, {"text": "나" * 3}], idx, None)
    assert "A-2" in bs[0]["segs"] and "A-1" not in bs[0]["segs"]


def test_충분하면_아무것도_안_붙인다():
    idx = _idx(("A-0", 2.0, "x"), ("A-1", 2.0, "y"))
    bs = [{"segs": ["A-0"]}]
    am.ensure_cover(bs, [{"text": "가" * 6}], idx, None)
    assert bs[0]["segs"] == ["A-0"]
