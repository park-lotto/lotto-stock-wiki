"""자료 → 프롬프트 → Gemini. 모델 교체 지점을 여기 하나로 묶는다."""
from shopping_shorts import bot_answer


HITS = [{"id": 1, "question": "포인트는 어떻게 사나요",
         "answer": "설정 화면에서 충전합니다.", "tags": "포인트"}]


def test_prompt_contains_the_material():
    p = bot_answer.build_prompt("포인트 어떻게 사요", HITS)
    assert "설정 화면에서 충전합니다." in p


def test_prompt_forbids_going_outside_material():
    """★프롬프트에 '자료 밖은 답하지 마라'가 반드시 있어야 한다."""
    p = bot_answer.build_prompt("포인트 어떻게 사요", HITS)
    assert "자료" in p and ("밖" in p or "없" in p)


def test_answer_uses_gemini_and_appends_source(monkeypatch):
    monkeypatch.setattr(bot_answer, "_call", lambda prompt: {"answer": "충전하시면 됩니다"})
    out = bot_answer.answer("포인트 어떻게 사요", HITS)
    assert "충전하시면 됩니다" in out
    assert "포인트는 어떻게 사나요" in out, "근거 표시가 있어야 틀린 답을 바로잡을 수 있다"


def test_empty_material_never_calls_model(monkeypatch):
    """★자료가 없으면 모델을 아예 안 부른다 — 지어내기 차단의 마지막 방어선."""
    called = []
    monkeypatch.setattr(bot_answer, "_call", lambda p: called.append(1) or {})
    assert bot_answer.answer("모르는 질문", []) is None
    assert called == [], "자료 없이 모델을 불렀다"


def test_model_failure_returns_none(monkeypatch):
    """키 소진·응답 오류는 {}로 온다 → 지어내지 말고 None."""
    monkeypatch.setattr(bot_answer, "_call", lambda p: {})
    assert bot_answer.answer("포인트", HITS) is None
