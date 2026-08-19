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
