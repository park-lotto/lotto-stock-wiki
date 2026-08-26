# -*- coding: utf-8 -*-
"""장면 근거 게이트 — 화면에 없는 재료가 대본에 박히지 않게 (2026-08-19).

사장님 지적: "장면에도 없는 대본이 나오는 거 아닌가" → 실측해보니 맞았다.
전사(=말)에서 뽑은 재료라 화면에 안 찍힌 값이 섞이고, 그대로 조립되면
"양말 누런 때부터"라고 말하는데 화면엔 양말이 없다.
"""
from shopping_shorts import insta_facts, spine_fill

SEGMENTS = [
    {"scene_desc": "욕실 수전에 세제를 뿌리는 모습"},
    {"scene_desc": "곰팡이가 낀 욕실 타일을 보여주는 장면"},
]


def test_화면에_없는_값은_버린다():
    facts = {"targets": ["욕실 수전 물때", "누렇게 변한 흰 양말"]}
    out = insta_facts.gate_by_scene(facts, SEGMENTS, log=lambda *a: None)
    assert out["targets"] == ["욕실 수전 물때"]


def test_말로만_하는_칸은_면제된다():
    """가격·수치·차별점·효과는 원래 카메라로 못 찍는다 — 검사하면 멀쩡한 재료가 죽는다."""
    facts = {"price": ["단돈 몇 천 원"], "numbers": ["5분"],
             "edge": ["판매 1위 제품"], "effects": ["새 것처럼 닦이는"]}
    out = insta_facts.gate_by_scene(facts, SEGMENTS, log=lambda *a: None)
    assert out == facts


def test_장면_인벤토리가_비면_그대로_통과한다():
    """근거가 없는 게 아니라 *모르는* 것이다. 여기서 거르면 무자막 소스가 통째로 죽는다."""
    facts = {"targets": ["누렇게 변한 흰 양말"], "how_to": ["물에 담가두기"]}
    assert insta_facts.gate_by_scene(facts, [], log=lambda *a: None) == facts
    assert insta_facts.gate_by_scene(facts, None, log=lambda *a: None) == facts


def test_다_걸리면_그_칸만_빈다():
    """빈 리스트를 담으면 '채워졌다'고 보고 빈칸이 대본에 나간다(spine_fill 규약)."""
    facts = {"targets": ["누렇게 변한 흰 양말"], "price": ["천 원"]}
    out = insta_facts.gate_by_scene(facts, SEGMENTS, log=lambda *a: None)
    assert "targets" not in out          # 키 자체가 없어야 한다(빈 리스트 아님)
    assert out["price"] == ["천 원"]


def test_후보가_남으면_칸은_안_빈다():
    """★게이트는 **재료 목록**을 거른다 — 하나 버려도 대체가 남아 칸이 유지된다.
    (slots_from_insta가 _first로 집은 뒤에 걸렀다면 대체가 없어 칸이 비었을 것)"""
    facts = {"targets": ["누렇게 변한 흰 양말", "욕실 수전 물때", "오래된 욕실 곰팡이"]}
    out = insta_facts.gate_by_scene(facts, SEGMENTS, log=lambda *a: None)
    slots = spine_fill.slots_from_insta(out)
    assert slots["적용대상"] == "욕실 수전 물때"       # 화면에 없는 첫 값이 밀려났다
    assert "양말" not in slots.get("적용대상들", "")


def test_판정은_공용_bigrams_한_벌이다():
    """0순위-B: 같은 판정을 두 군데 적지 않는다(_join_targets와 공용)."""
    assert insta_facts._grams("욕실 수전") == spine_fill.bigrams("욕실 수전")


def test_껍데기_말로는_통과하지_못한다():
    """scene_desc가 거의 전부 '~하는 모습'이라, 안 빼면 아무 값이나 통과한다."""
    facts = {"targets": ["보여주는 모습"]}
    out = insta_facts.gate_by_scene(facts, SEGMENTS, log=lambda *a: None)
    assert "targets" not in out
