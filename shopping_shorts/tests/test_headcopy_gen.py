"""고정카피 생성 — AI가 죽어도 화면이 죽지 않는가(fail-open)를 함께 잠근다."""
from shopping_shorts import headcopy_gen


def test_returns_four_copies(monkeypatch):
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        {"label": "짧은 훅형", "text": "이거 모르면 손해"},
        {"label": "숫자형", "text": "3초면 끝납니다"},
        {"label": "반전형", "text": "비싼 줄 알았는데"},
        {"label": "질문형", "text": "아직도 손으로 하세요?"},
    ]})
    out = headcopy_gen.suggest("대본 텍스트입니다")
    assert len(out) == 4
    assert out[0]["text"] == "이거 모르면 손해"
    assert out[0]["label"] == "짧은 훅형"


def test_empty_script_skips_ai_entirely(monkeypatch):
    """대본이 없으면 AI를 부르지 않는다 — 부르면 빈 재료로 지어내고 돈만 쓴다."""
    called = []
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: called.append(1) or {})
    assert headcopy_gen.suggest("   ") == []
    assert called == [], "빈 대본인데 AI를 불렀다"


def test_ai_failure_returns_empty_not_crash(monkeypatch):
    """_call_json은 실패 시 {}를 준다(fail-open). 그걸 그대로 흘리면 화면이 깨진다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {})
    assert headcopy_gen.suggest("대본") == []


def test_drops_blank_and_overlong(monkeypatch):
    """빈 문구·너무 긴 문구는 버린다 — 헤드카피는 화면에 크게 박히는 한 줄이다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        {"label": "a", "text": "  "},
        {"label": "b", "text": "정상 문구"},
        {"label": "c", "text": "가" * 200},
    ]})
    out = headcopy_gen.suggest("대본")
    assert [c["text"] for c in out] == ["정상 문구"]


def test_dedupes_identical_text(monkeypatch):
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        {"label": "a", "text": "같은 문구"},
        {"label": "b", "text": "같은 문구"},
        {"label": "c", "text": "다른 문구"},
    ]})
    assert [c["text"] for c in headcopy_gen.suggest("대본")] == ["같은 문구", "다른 문구"]
