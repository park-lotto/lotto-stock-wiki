# -*- coding: utf-8 -*-
"""인스타 조립 경로 배선 — 다이소 스파인이 라이브 조립 경로를 탄다 (2026-08-19).

지금까지 `insta_facts`는 실험실에서만 돌았다(app.py에서 부르는 곳이 0곳).
이 테스트가 배선을 붙잡는다 — 갈래 판정 · 재료 추출기 선택 · 장면 게이트 통과까지.

★Gemini는 부르지 않는다. 추출기를 monkeypatch로 갈아끼워 **배선만** 본다
  (모델 호출은 느리고 돈이 들며, 여기서 보려는 건 배선이 맞물리는가다).
"""
from shopping_shorts import app, insta_facts

DAISO_SPINE = {
    "id": 99, "name": "다이소 내부인형",
    "fit_categories": ["다이소형"],
    "chars_per_30s": 226,
    "beat_roles": ["hook", "problem", "demo", "result"],
    "templates": {
        "hook": ["여러분 다이소 가면 이거 무조건 사오세요"],
        "problem": ["아니 {불편함} 때문에 진짜 스트레스였거든요"],
        "demo": ["방법도 진짜 간단해요. {사용법}, 이게 끝이에요"],
        "result": ["와 {적용대상들} {효과} 거 있죠"],
    },
}

SOURCES = [{
    "name": "다이소 욕실세정제",
    "full_text": "욕실 곰팡이가 안 지워져서 고생했는데 이거 뿌리니까 싹 없어져요",
    "segments": [
        {"scene_desc": "욕실 수전에 세제를 뿌리는 모습"},
        {"scene_desc": "곰팡이가 낀 욕실 타일을 보여주는 장면"},
    ],
}]

FACTS = {
    "how_to": ["욕실에 칙칙 뿌리고 물로 헹구기"],
    "targets": ["누렇게 변한 흰 양말", "욕실 수전 물때", "오래된 욕실 곰팡이"],
    "pain": ["아무리 닦아도 안 지워지던 곰팡이"],
    "effects": ["완전 새 것처럼 닦이는"],
}


def _patch(monkeypatch, facts=FACTS):
    monkeypatch.setattr(insta_facts, "analyze_insta", lambda raw, **kw: dict(facts))


def test_다이소_스파인은_인스타_갈래로_잡힌다():
    assert app._is_insta_context("", [DAISO_SPINE]) is True
    assert app._is_sul_context("", [DAISO_SPINE]) is False


def test_다이소_스파인이_조립본을_만든다(monkeypatch):
    _patch(monkeypatch)
    out, left, why = app._assembled_drafts([DAISO_SPINE], SOURCES, None, seconds=30)
    assert len(out) == 1, "조립본이 안 나왔다: left=%s why=%s" % (len(left), why)
    assert not left


def test_화면에_없는_재료는_조립본에_안_박힌다(monkeypatch):
    """★이 배선의 요점 — 전사에 있어도 화면에 없으면 대본에 못 들어간다."""
    _patch(monkeypatch)
    out, _left, _why = app._assembled_drafts([DAISO_SPINE], SOURCES, None, seconds=30)
    text = " ".join(b.get("text", "") for b in (out[0].get("beats") or []))
    assert "양말" not in text, text          # 화면에 양말이 없다
    assert "곰팡이" in text                  # 화면에 있는 값으로 대체됐다


def test_장면이_없으면_그대로_통과한다(monkeypatch):
    """무자막·미태깅 소스에서 재료가 조용히 전멸하면 안 된다."""
    _patch(monkeypatch)
    src = [{"name": "x", "full_text": SOURCES[0]["full_text"], "segments": []}]
    out, _left, _why = app._assembled_drafts([DAISO_SPINE], src, None, seconds=30)
    assert len(out) == 1


def test_재료가_없으면_기존_생성기로_넘긴다(monkeypatch):
    """조립 못 하면 폴백하되 **이유를 남긴다**(조용한 폴백 금지)."""
    _patch(monkeypatch, facts={})
    out, left, why = app._assembled_drafts([DAISO_SPINE], SOURCES, None, seconds=30)
    assert not out and len(left) == 1
    assert why, "왜 조립을 못 했는지 화면에 말해야 한다"


def test_썰_스파인은_인스타_추출기를_안_쓴다(monkeypatch):
    """갈래가 섞이면 안 된다 — 유튜브 스파인에 인스타 추출기가 돌면 재료가 어긋난다."""
    called = []
    monkeypatch.setattr(insta_facts, "analyze_insta",
                        lambda raw, **kw: called.append(1) or {})
    sul = dict(DAISO_SPINE, fit_categories=["오용형"])
    app._assembled_drafts([sul], SOURCES, None, seconds=30)
    assert not called
