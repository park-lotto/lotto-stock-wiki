"""화면 제목 길이 — 프롬프트 안내와 게이트가 template_copy 한 곳의 수를 본다(2026-09-18)."""
import pytest
from shopping_shorts import bank_assemble, canary, script_gate
from shopping_shorts.template_copy import EVEN_SHOPPING


@pytest.fixture(autouse=True)
def canary_on():
    """이 파일의 계약은 관리자 카나리 안에서만 켜진다(2026-09-18). 고객 기본값은 꺼짐."""
    canary.set_active(True)
    yield
    canary.set_active(False)


def _style():
    return {"name": "t", "beat_roles": ["title", "story"], "beat_descs": {"title": "궁금증"},
            "templates": {}}


def test_title_desc_carries_len_rule():
    st = bank_assemble.with_spoken_hook(_style())
    assert st["beat_roles"] == ["title", "story"]
    assert ("%d자 이내" % (EVEN_SHOPPING.hook_line_max * 2)) in st["beat_descs"]["title"]
    assert st["beat_descs"]["title"].startswith("궁금증")


def test_gate_flags_long_title_not_fatal():
    st = bank_assemble.with_spoken_hook(_style())
    long_t = "제조사도 예상 못한 움직이는 기차 케이크 활용법"   # 27자(실측 사고)
    beats = [{"role": "title", "text": long_t}, {"role": "story", "text": "사연임"}]
    checks, _ = script_gate.check(st, beats)
    c = next(x for x in checks if x["name"] == "화면 제목 길이")
    assert c["ok"] is False and not c.get("fatal")
    beats[0]["text"] = "제조사도 놀란 기차 케이크"           # 14자
    checks, _ = script_gate.check(st, beats)
    assert next(x for x in checks if x["name"] == "화면 제목 길이")["ok"] is True


def test_gate_skips_non_title_styles():
    checks, _ = script_gate.check({"beat_roles": ["hook"], "templates": {}}, [{"role": "hook", "text": "a"}])
    assert not any(x["name"] == "화면 제목 길이" for x in checks)
