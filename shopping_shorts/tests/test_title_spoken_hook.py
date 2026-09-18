"""제목형 = 이븐쇼핑 원본 구조: 제목이 첫 TTS이자 화면 큰 제목(2026-09-18 실측 ABjQ0YCZoes)."""
import pytest
from shopping_shorts import bank_assemble, canary


@pytest.fixture(autouse=True)
def canary_on():
    canary.set_active(True)
    yield
    canary.set_active(False)


def _legacy_style():
    return {"id": 60, "name": "t", "beat_roles": ["title", "story", "benefit"],
            "beat_descs": {"title": "궁금증"}, "templates": {"title": ["{나라} 개발자도 놀란 {제품}"]}}


def test_제목칸은_그대로_첫칸이고_읽는다는_안내와_글자한도가_붙는다():
    old = _legacy_style()
    got = bank_assemble.with_spoken_hook(old)
    assert got["beat_roles"] == ["title", "story", "benefit"]
    assert "목소리 첫 문장" in got["beat_descs"]["title"] and "11자" in got["beat_descs"]["title"]
    assert got["title_visual_only"] is True
    assert old == _legacy_style(), "DB 원본을 제자리에서 바꾸면 안 된다"


def test_두번_통과해도_같다():
    st = bank_assemble.with_spoken_hook(_legacy_style())
    assert bank_assemble.with_spoken_hook(st) is st


def test_제목형이_아니면_건드리지_않는다():
    st = {"beat_roles": ["hook", "story"], "templates": {}}
    assert bank_assemble.with_spoken_hook(st) is st
