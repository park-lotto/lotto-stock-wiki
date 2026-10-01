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


def test_fill_stops_at_different_scene(monkeypatch):
    """같은 영상 다음 컷이 딴 장면(label 다름)이면 채우지 않는다 — 배수구 다음 감자(2026-10-01)."""
    idx = {
        "s1-38": {"secs": 0.8, "desc": "배수구로 물 버림", "vid": "s1", "role": "실증", "label": "물 빼기 과정", "outro": False},
        "s1-39": {"secs": 0.9, "desc": "익은 감자 가득", "vid": "s1", "role": "after", "label": "조리 후 결과 확인", "outro": False},
        "s1-40": {"secs": 0.8, "desc": "완성 요리 접시", "vid": "s1", "role": "완성", "label": "제품 활용 예시", "outro": False},
        "s0-0": {"secs": 3.0, "desc": "씨앗", "vid": "s0", "role": "완성", "label": "", "outro": False},
    }
    monkeypatch.setattr(am._sg, "_call_json", lambda *a, **k: {"picks": [{"line": 1, "cuts": ["s1-38"], "why": "x"}]})
    out = am.match([{"role": "고조1", "text": "뜨거운 물 버리다 손 데이고 싱크대에 면발을 쏟던 지옥을"}], idx, "s0", note={})
    assert out and out[0]["segs"] == ["s1-38"], out


def test_lock_does_not_repeat_same_cut_across_group_lines():
    """묶음 안 여러 줄을 고정할 때 같은 컷을 또 박지 않는다 — 고조1 세 줄 = 같은 배수구 컷(2026-10-01)."""
    import io as _io, os as _os, re as _re
    src = _io.open(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "story_writer.py"), encoding="utf-8").read()
    body = src[src.index("_locked = 0"):src.index('n["locked_lines"]')]
    assert "_taken" in body and "allowed[:1]" in body
    # allowed[:1] 로 떨어지기 전에 '안 쓴 컷'을 먼저 고르는 줄이 있어야 한다
    assert _re.search(r"c not in _taken", body)
