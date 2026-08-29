# -*- coding: utf-8 -*-
"""Gemini 호흡 끊기(ai_breath_lines, 2026-08-29 사장님 "자연스러운 호흡이 기본") —
caption_lines가 없는 폴백 칸만 이해 기반 분할로 채운다. 실패·불일치·테스트 중엔 None
(=규칙 폴백 그대로)이라 어떤 경우에도 종전보다 나빠질 수 없다.

⚠️ ai_breath_lines는 PYTEST_CURRENT_TEST 가드로 테스트에선 즉시 None이다(.env 실키
로컬에서 pytest가 네트워크를 타면 게이트가 느려지고 흔들린다). 로직을 검증하는
테스트는 monkeypatch.delenv로 가드를 걷고 _call_json을 목으로 막는다.
"""
import pytest

from shopping_shorts import script_generate
from shopping_shorts import mix_pipeline

NARR = "인테리어 고수들만 안다는 비밀 테이블이 있어요"


def _ungate(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


def test_valid_lines_returned(monkeypatch):
    _ungate(monkeypatch)
    monkeypatch.setattr(script_generate, "_call_json",
                        lambda p, s: {"lines": ["인테리어 고수들만 안다는", "비밀 테이블이 있어요"]})
    assert script_generate.ai_breath_lines(NARR) == ["인테리어 고수들만 안다는", "비밀 테이블이 있어요"]


def test_mutated_text_discarded(monkeypatch):
    """글자가 하나라도 바뀌면(추가·수정·누락) 폐기 — 자막이 대본과 어긋나면 안 된다."""
    _ungate(monkeypatch)
    monkeypatch.setattr(script_generate, "_call_json",
                        lambda p, s: {"lines": ["인테리어 고수들만 아는", "비밀 테이블이 있어요"]})
    assert script_generate.ai_breath_lines(NARR) is None


def test_trailing_punct_tolerated_like_renderer(monkeypatch):
    """대조 기준은 cap_preset_key 한 곳(0순위-B) — 렌더가 받아줄 줄(끝 마침표 차이)을
    여기서 다른 기준으로 버리면 안 된다."""
    _ungate(monkeypatch)
    monkeypatch.setattr(script_generate, "_call_json",
                        lambda p, s: {"lines": ["인테리어 고수들만 안다는", "비밀 테이블이 있어요"]})
    assert script_generate.ai_breath_lines(NARR + ".") == \
        ["인테리어 고수들만 안다는", "비밀 테이블이 있어요"]


def test_empty_or_short_skips_call(monkeypatch):
    """빈 문장·아주 짧은 문장은 호출 자체를 안 한다(규칙이 충분, 비용 0)."""
    _ungate(monkeypatch)
    called = []
    monkeypatch.setattr(script_generate, "_call_json",
                        lambda p, s: called.append(1) or {"lines": ["짧다"]})
    assert script_generate.ai_breath_lines("") is None
    assert script_generate.ai_breath_lines("짧은 문장") is None
    assert called == []


def test_pytest_guard_blocks_network():
    """가드가 있는 그대로(=이 테스트 환경)면 _call_json까지 안 간다."""
    assert script_generate.ai_breath_lines(NARR) is None


def test_ensure_breath_lines_fills_only_missing(monkeypatch):
    """재합성 관문 헬퍼 — 이미 있으면 안 건드리고, 없으면 AI 결과를 채운다."""
    monkeypatch.setattr(script_generate, "ai_breath_lines",
                        lambda n: ["인테리어 고수들만 안다는", "비밀 테이블이 있어요"])
    beat = {"narration": NARR, "caption_lines": None}
    mix_pipeline._ensure_breath_lines(beat)
    assert beat["caption_lines"] == ["인테리어 고수들만 안다는", "비밀 테이블이 있어요"]

    kept = ["원래", "있던 줄"]
    beat2 = {"narration": NARR, "caption_lines": kept}
    mix_pipeline._ensure_breath_lines(beat2)
    assert beat2["caption_lines"] is kept


def test_ensure_breath_lines_survives_ai_crash(monkeypatch):
    """AI 쪽 예외가 합성을 죽이면 안 된다 — 조용히 규칙 폴백."""
    def boom(n):
        raise RuntimeError("network down")
    monkeypatch.setattr(script_generate, "ai_breath_lines", boom)
    beat = {"narration": NARR, "caption_lines": None}
    mix_pipeline._ensure_breath_lines(beat)
    assert beat["caption_lines"] is None
