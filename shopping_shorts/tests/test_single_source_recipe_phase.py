# -*- coding: utf-8 -*-
"""레시피 페이즈 배치 (2026-08-06 사장님): 완성품 훅 → 재료 → 조리 한 덩어리 → 완성품.
조리가 틈틈이 쪼개져 들어가는 게 어색하다 — 비법 구간 한 번이면 충분."""
from shopping_shorts.single_source import select_and_order

SEGS = [
    {"seg_id": "a", "start": 0, "end": 3, "shot_role": "before", "is_key": False},
    {"seg_id": "b", "start": 3, "end": 6, "shot_role": "사용중", "is_key": True},
    {"seg_id": "c", "start": 6, "end": 9, "shot_role": "after", "is_key": True},
    {"seg_id": "d", "start": 9, "end": 12, "shot_role": "사용중", "is_key": False},
    {"seg_id": "e", "start": 12, "end": 15, "shot_role": "after", "is_key": False},
]


def test_레시피는_완성품훅_조리한덩어리():
    _, _, _, o = select_and_order([dict(s) for s in SEGS], 15, video_type="recipe")
    roles = [s["shot_role"] for s in o]
    assert roles[0] == "after", roles                       # 훅 = 완성품
    cook = [i for i, r in enumerate(roles) if r == "사용중"]
    assert cook == list(range(cook[0], cook[0] + len(cook))), roles  # 조리는 연속 블록


def test_레시피_페이즈는_끌_수_있다(monkeypatch):
    monkeypatch.setenv("SCENE_PHASE_ORDER", "0")
    _, _, _, off = select_and_order([dict(s) for s in SEGS], 15, video_type="recipe")
    _, _, _, gen = select_and_order([dict(s) for s in SEGS], 15)
    assert [s["seg_id"] for s in off] == [s["seg_id"] for s in gen]  # off = 종전 동일


def test_generic은_종전_순서_그대로():
    _, _, _, o = select_and_order([dict(s) for s in SEGS], 15)
    assert [s["seg_id"] for s in o] == ["c", "b", "d", "a", "e"]
