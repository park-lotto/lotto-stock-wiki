# -*- coding: utf-8 -*-
"""ai_match: 뒷컷은 목록·검증·채우기 어디서도 안 쓰고, 훅 유형을 AI 에게 보여준다 (2026-10-01, 카드 055 라이브 실측 사고).
고치기 전: AI 가 고른 뒷컷(인사)이 그대로 통과했다 → 이 검사가 FAIL."""
from shopping_shorts import ai_match as am


def _idx():
    return {
        "s1-0": {"secs": 3.0, "desc": "엄지 치켜세우며 인사", "vid": "s1", "role": "after", "hook": "", "outro": True},
        "s1-1": {"secs": 3.0, "desc": "접힌 막대가 십자로 펴짐", "vid": "s1", "role": "조작", "hook": "반전", "outro": False},
        "s1-2": {"secs": 3.0, "desc": "제품 외관", "vid": "s1", "role": "완성", "hook": "", "outro": False},
        "s0-0": {"secs": 3.0, "desc": "씨앗 원본", "vid": "s0", "role": "완성", "hook": "", "outro": False},
    }


def test_cut_block_hides_outro_and_shows_hook():
    idx = _idx()
    blk = am._cut_block(idx, "s0", sorted(idx))
    assert "s1-0" not in blk and "s0-0" not in blk
    assert "s1-1" in blk and "훅:반전" in blk


def test_ai_pick_of_outro_is_dropped_and_not_filled_with_outro(monkeypatch):
    idx = _idx()
    monkeypatch.setattr(am._sg, "_call_json", lambda *a, **k: {"picks": [{"line": 1, "cuts": ["s1-0", "s1-2"], "why": "x"}]})
    out = am.match([{"role": "훅", "text": "해외 천재가 만든 제품의 정체"}], idx, "s0", note={})
    assert out and out[0]["segs"] == ["s1-2"], out


def test_brief_mentions_hook_rule():
    assert "훅:" in am.BRIEF and "미끼" in am.BRIEF
