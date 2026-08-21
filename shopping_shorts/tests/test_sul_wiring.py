# -*- coding: utf-8 -*-
"""썰 재료가 **실제 대본 생성 경로에 배선돼 있는가**(2026-08-19).

모듈만 있고 아무도 안 부르면 없는 것과 같다 — 실제로 그 상태였다
(handoff/썰쇼핑대본재료.md ⏭ 1번). 여기서 못을 박는다.
"""
import shopping_shorts.app as app


def test_썰카테고리만_추출한다():
    """카테고리가 아니면 Gemini를 아예 안 부른다(호출 1회 절약 + 회귀 0)."""
    called = []

    class _Fake:
        @staticmethod
        def analyze_sul(raw, **kw):
            called.append(raw)
            return {"original_use": ["의류 태그 부착"]}

        @staticmethod
        def sul_prompt_block(facts, **kw):
            return "[블록]" if facts else ""

    # ★sys.modules만 바꾸면 안 된다 — `from shopping_shorts import sul_facts`는
    #   이미 임포트된 경우 **패키지 속성**을 먼저 본다(다른 테스트가 먼저 임포트하면
    #   스텁이 조용히 무시돼 이 테스트가 순서에 따라 깨진다. 실측 2026-08-19).
    import shopping_shorts as _pkg
    _orig = getattr(_pkg, "sul_facts", None)
    _pkg.sul_facts = _Fake
    try:
        src = [{"full_text": "이게 원래는 태그 붙이는 용도였음"}]
        assert app._sul_block_for_sources("홈템", src, None) == ""
        assert called == []
        assert app._sul_block_for_sources("오용형", src, None) == "[블록]"
        assert len(called) == 1
        assert app._sul_block_for_sources("제품정체형", src, None) == "[블록]"
        # ★라이브 실제 모양(2026-08-19 실측): 항목 category는 '홈템'이고
        #   썰 여부는 **고른 스파인의 fit_categories**로만 갈린다.
        #   이걸 안 보면 배선이 살아 있어도 라이브에서 영영 안 켜진다.
        _sul_spine = {"id": 56, "name": "유튜브 오용형", "fit_categories": ["오용형"]}
        assert app._sul_block_for_sources("홈템", src, None, [_sul_spine]) == "[블록]"
        assert app._sul_block_for_sources(
            "홈템", src, None, [{"fit_categories": ["홈템"]}]) == ""
    finally:
        if _orig is not None:
            _pkg.sul_facts = _orig


def test_재료없으면_빈문자열():
    assert app._sul_block_for_sources("오용형", [], None) == ""
    assert app._sul_block_for_sources("오용형", [{"full_text": "  "}], None) == ""


def test_추출실패해도_대본을_막지_않는다():
    class _Boom:
        @staticmethod
        def analyze_sul(raw, **kw):
            raise RuntimeError("키 소진")

    import shopping_shorts as _pkg
    _orig = getattr(_pkg, "sul_facts", None)
    _pkg.sul_facts = _Boom
    try:
        assert app._sul_block_for_sources("오용형", [{"full_text": "x"}], None) == ""
    finally:
        if _orig is not None:
            _pkg.sul_facts = _orig


def test_생성경로가_이_함수를_부른다():
    """★_materials_for_generate가 부르지 않으면 배선이 죽은 것이다."""
    import inspect
    src = inspect.getsource(app._materials_for_generate)
    assert "_sul_block_for_sources" in src


def test_라이브_스파인_모양으로_판정된다():
    """실측 근거: spine 55·56의 fit_categories가 ["제품정체형"]·["오용형"]이고,
    위키 항목 113건 중 이 카테고리를 가진 항목은 **0건**이었다(2026-08-19 서버 DB)."""
    assert app._is_sul_context("홈템", [{"fit_categories": ["오용형"]}]) is True
    # ★2026-08-21: 은폐형(제품정체형)을 썰에서 **갈라냈다**. 같은 트랙에 두면
    #   `sul_material_problem`(="원래 용도를 뒤집는가")을 타서 통째로 막힌다 —
    #   은폐형은 뒤집는 갈래가 아니라 정체를 숨겼다 밝히는 갈래다.
    #   실측: 사장님 구명 팔찌 소재에서 "이 영상은 오용형이 아닙니다"로 차단됐다.
    assert app._is_sul_context("홈템", [{"fit_categories": ["제품정체형"]}]) is False
    assert app._is_conceal_context("홈템", [{"fit_categories": ["제품정체형"]}]) is True
    assert app._is_sul_context("홈템", [{"fit_categories": ["홈템", "기타"]}]) is False
    assert app._is_sul_context("홈템", [{"fit_categories": None}]) is False
    assert app._is_sul_context("오용형", None) is True
    assert app._is_sul_context("", None) is False


def test_호출부가_스파인을_넘긴다():
    """★넘기지 않으면 게이트가 영영 안 켜진다 — 배선만 있고 죽은 상태."""
    import inspect
    src = inspect.getsource(app)
    assert "spines=_picked" in src, "전체 생성이 고른 스파인을 안 넘긴다"
    assert "spines=[style]" in src, "[바꾸기] 재생성이 스파인을 안 넘긴다"
