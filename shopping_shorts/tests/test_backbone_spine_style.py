# -*- coding: utf-8 -*-
"""조립기가 스파인 문장틀·역할순서를 그대로 쓰는지(2026-09-17 사장님: "이븐쇼핑 스타일" = 천재·떼돈·「이건 바로 OO」·CTA 없음)."""
from shopping_shorts import backbone_assemble as ba

ROLES = ["title", "bait", "fame", "reveal", "limit", "solve", "more", "twist", "land"]
TPL = {"title": ["{나라} 천재가 만들어 떼돈 번 {제품군}의 정체"], "bait": ["평범한 이 {제품군}가"],
       "fame": ["천재가 떼돈을 벌었다는데"], "reveal": ["이건 바로 {제품}"], "limit": ["기존 {제품군}은 한계였는데"],
       "solve": ["이건 {효능}"], "more": ["심지어 {효능2}"], "twist": ["진짜 충격은 {효능3}"], "land": ["이러니 떼돈을 벌었다고"]}


def test_효능_자리만_특징줄이다():
    assert ba._feature_roles(ROLES, TPL) == ["solve", "more", "twist"]


def test_특징3개면_틀_그대로_9줄():
    plan = ba._spine_plan(ROLES, TPL, 3)
    assert [r for r, _ in plan] == ROLES
    assert [g for _, g in plan] == [-1, -1, -1, -1, -1, 0, 1, 2, -1]


def test_특징이_많으면_more를_twist_앞에_반복():
    plan = ba._spine_plan(ROLES, TPL, 5)
    assert [r for r, _ in plan] == ["title", "bait", "fame", "reveal", "limit", "solve", "more", "more", "more", "twist", "land"]
    assert [g for _, g in plan if g >= 0] == [0, 1, 2, 3, 4]


def test_특징이_적으면_남는_효능줄을_뺀다():
    plan = ba._spine_plan(ROLES, TPL, 1)
    assert [r for r, _ in plan] == ["title", "bait", "fame", "reveal", "limit", "solve", "land"]


def test_프롬프트에_CTA_금지와_문장틀이_들어간다():
    p = ba._spine_prompt({"product": "카메라", "order": [0, 1, 2]}, {"name": "이건 바로 OO"}, ROLES, TPL, ["  1. [0] a", "  2. [1] b", "  3. [2] c"], 20)
    assert "이건 바로 {제품}" in p and "CTA를 덧붙이지 마라" in p and "role=twist" in p


def test_틀_없는_스파인은_옛_경로():
    assert ba._spine_style({"name": "x"}) == ([], {})
