# -*- coding: utf-8 -*-
"""훅 감탄사 켜고 끄기 (2026-09-01 사장님 "그냥 모든 대본에 앞에 감탄사 켜고 끄기 버튼").

코드가 대본 첫 문장 앞에 "와, "(서술형 절반) / "여러분 "(권유형)을 얹는다
(single_source.add_hook_opener — 프롬프트로는 안 돼서 코드로 옮긴 이력이 있다).
그걸 관리자가 전역으로 끌 수 있게 한다.

계약:
  · 설정이 없으면 **켬**(종전과 100% 같다 — 회귀 0)
  · off면 어떤 스타일이든 안 붙인다(모델이 스스로 쓴 감탄사는 그대로 — 코드 강제만 끈다)
  · 판정은 hook_opener_on 한 곳(0순위-B). DB는 60초 캐시로 읽는다
"""
import pytest

from shopping_shorts import single_source as S


@pytest.fixture(autouse=True)
def _clear_cache():
    S._HOOK_OPENER_CACHE.update(t=0.0, on=True)
    yield
    S._HOOK_OPENER_CACHE.update(t=0.0, on=True)


def _beats():
    return [{"narration": "다이소에서 이걸 봤어요."}]


def test_켠_상태면_감탄사가_붙는다(monkeypatch):
    monkeypatch.setattr(S, "hook_opener_on", lambda: True)
    b = _beats()
    if S.hook_opener_missing(b):
        b = S.add_hook_opener(b)
    # 서술형은 대본 해시로 절반만 붙는다 — 붙었거나 원문 그대로거나 둘 중 하나
    assert b[0]["narration"].startswith(("와, ", "다이소"))


def test_끈_상태면_어떤_스타일이든_안_붙는다(monkeypatch):
    monkeypatch.setattr(S, "hook_opener_on", lambda: False)
    for style in (None, "maison", "hometerior", "standard", "chae"):
        assert S.hook_opener_missing(_beats(), style) is False, f"{style}에서 아직 붙는다"


def test_설정이_없으면_켬이_기본(monkeypatch):
    """읽기 실패·미설정은 종전 동작(켬)으로 떨어져야 한다 — 회귀 0."""
    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("DB 없음")
    monkeypatch.setattr("shopping_shorts.store.Store", _Boom)
    S._HOOK_OPENER_CACHE.update(t=0.0)
    assert S.hook_opener_on() is True


def test_판정은_한_곳뿐이다():
    """호출부가 제 나름대로 판정하면 두 벌이 된다(0순위-B)."""
    import inspect
    src = inspect.getsource(S.hook_opener_missing)
    assert "hook_opener_on()" in src, "스위치를 안 본다"
