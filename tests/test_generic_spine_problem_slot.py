# -*- coding: utf-8 -*-
"""generic 스파인의 문제상황 슬롯 — 2026-08-17 실측으로 추가된 것을 고정한다.

왜 이 테스트가 필요한가(실사고): generic 스파인 4슬롯 어디에도 before·문제가 없어
그 조각들이 **원천 제외**됐다. 대본은 problem 비트를 만드는데 화면 스파인엔 그 자리가
없어 아무거나 붙었다(job d6520c0c4c80: before 4개 보유했는데 problem 비트엔 '사용중'
하나만 배정). 슬롯을 지우면 같은 사고가 조용히 재발하므로 여기서 못박는다.

★두 번째 테스트가 핵심이다 — "슬롯을 늘렸더니 원래 되던 게 망가졌다"를 막는 안전장치.
"""
from shopping_shorts import edit_plan as ep


def _seg(sid, role, key=False, start=0):
    return {"seg_id": sid, "shot_role": role, "is_key": key, "start": start,
            "scene_desc": f"{role} 장면"}


def _slots(out):
    return [(b["slot"], b["seg_id"]) for b in out]


def test_before_보유하면_문제상황_슬롯이_그것을_집는다():
    """실측 재현(요거트 job): before가 있으면 problem 자리에 before가 들어간다."""
    segs = {s["seg_id"]: s for s in [
        _seg("완성1", "완성", True, 1), _seg("before1", "before", False, 3),
        _seg("사용1", "사용중", True, 5), _seg("after1", "after", False, 9),
        _seg("기타1", "기타", False, 12)]}
    got = _slots(ep._build_scene_spine(segs, "generic"))
    assert ("문제상황", "before1") in got
    # 훅 다음, 실증 앞 — 순서까지 고정(대본 problem 비트 위치와 맞아야 한다)
    assert [s for s, _ in got][:3] == ["강한장면훅", "문제상황", "핵심실증"]


def test_before가_없으면_슬롯추가_전과_완전히_동일하다():
    """★안전장치: 0건 소재(젬펜 등)는 종전 배치가 한 글자도 안 바뀌어야 한다.

    _pick이 역할 맞는 조각을 못 찾으면 그 슬롯을 건너뛰기 때문이다 — 이 성질이 깨지면
    슬롯 추가가 곧 회귀가 된다."""
    segs = {s["seg_id"]: s for s in [
        _seg("완성1", "완성", True, 1), _seg("사용1", "사용중", True, 5),
        _seg("사용2", "사용중", False, 8), _seg("완성2", "완성", False, 11),
        _seg("기타1", "기타", False, 14)]}
    got = _slots(ep._build_scene_spine(dict(segs), "generic"))
    assert got == [("강한장면훅", "완성1"), ("핵심실증", "사용1"),
                   ("결과", "완성2"), ("CTA", "기타1")]
    assert not any(s == "문제상황" for s, _ in got)


def test_문제상황_슬롯이_generic에_실제로_박혀있다():
    """정의 자체를 고정 — 누가 지우면 여기서 걸린다."""
    roles = [tuple(s.get("roles", [])) for s in ep.VIDEO_TYPES["generic"]["spine"]
             if s["slot"] == "문제상황"]
    assert roles == [("before", "문제")]
