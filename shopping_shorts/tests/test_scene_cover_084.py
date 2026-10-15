# -*- coding: utf-8 -*-
"""관제 084: 2단계 장면 보장 — 줄마다 장면 길이 합×1.2 ≥ 대사. 같은 의미 장면 먼저, 없으면 원본 다음 장면."""
from shopping_shorts import ai_match as am


def _idx():
    return {"a-0": {"secs": 1.0, "vid": "a", "label": "커피 추출", "outro": False},
            "a-1": {"secs": 1.5, "vid": "a", "label": "컵 들기", "outro": False},
            "b-3": {"secs": 1.2, "vid": "b", "label": "커피 추출", "outro": False},
            "b-4": {"secs": 2.0, "vid": "b", "label": "인사", "outro": True}}


def test_same_meaning_first_then_next_in_source():
    lines = [{"text": "가" * 17}]                       # 약 3초
    bs = [{"role": "고조", "seg": "a-0", "segs": ["a-0"]}]
    n = {}
    am.ensure_cover(bs, lines, _idx(), None, note=n)
    assert bs[0]["segs"][:2] == ["a-0", "b-3"]           # 같은 쓰임(커피 추출) 다른 영상이 먼저
    assert n["cover_added"] >= 1


def test_never_uses_outro_or_other_lines_cuts():
    lines = [{"text": "가" * 30}, {"text": "나" * 5}]
    bs = [{"role": "고조", "seg": "b-3", "segs": ["b-3"]}, {"role": "마무리", "seg": "a-1", "segs": ["a-1"]}]
    n = {}
    am.ensure_cover(bs, lines, _idx(), None, note=n)
    assert "b-4" not in bs[0]["segs"] and "a-1" not in bs[0]["segs"]
    assert 0 in n["cover_short"]                         # 재료가 끝내 모자라면 기록(대사 줄이기 대상)


def test_enough_lines_untouched():
    lines = [{"text": "가" * 5}]
    bs = [{"role": "훅", "seg": "a-1", "segs": ["a-1"]}]
    am.ensure_cover(bs, lines, _idx(), None)
    assert bs[0]["segs"] == ["a-1"]
