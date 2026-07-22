"""대사가 영상보다 길 때 자동조정(콘폼) — Gemini 실패/쿼터여도 결정적으로 줄인다
(2026-07-22 사장님 요청: '이럴때는 대본을 자동조정하는걸 만들어줘야지')."""
from shopping_shorts import edit_plan


def _clen(s):
    return len("".join(s.split()))


def test_trim_drops_filler_to_fit():
    # '계란물을 모두 부어요' → 예산 짧으면 군더더기 '모두'를 빼 문법 유지하며 줄인다.
    out = edit_plan._trim_to_budget("계란물을 모두 부어요", char_target=6)
    assert out == "계란물을 부어요"


def test_trim_none_when_already_short():
    assert edit_plan._trim_to_budget("부어요", char_target=10) is None


def test_trim_none_when_no_filler_removable():
    # 뺄 군더더기가 없으면 원문 유지(억지 훼손 안 함).
    assert edit_plan._trim_to_budget("계란을 부어요", char_target=3) is None


def test_conform_falls_back_when_gemini_fails(monkeypatch):
    # Gemini(_vault_call)가 실패(None)해도 결정적 폴백으로 자동조정된다.
    monkeypatch.setattr(edit_plan, "_vault_call", lambda *a, **k: None)
    target = 6 / edit_plan._SYLLABLES_PER_SEC   # char_target≈6
    out = edit_plan.conform_narration("계란물을 모두 부어요", target)
    assert out == "계란물을 부어요"


def test_conform_gemini_success_used(monkeypatch):
    # Gemini가 예산 내 결과를 주면 그걸 쓴다(폴백 안 탐).
    monkeypatch.setattr(edit_plan, "_vault_call",
                        lambda *a, **k: {"narration": "계란 부어요"})
    target = 6 / edit_plan._SYLLABLES_PER_SEC
    assert edit_plan.conform_narration("계란물을 모두 천천히 부어요", target) == "계란 부어요"
