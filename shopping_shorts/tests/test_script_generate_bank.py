"""부품은행 컨텍스트가 실제 생성 프롬프트에 실리는지 — 가짜 Gemini로 프롬프트 포착.
bank_context 기본값(빈)이면 프롬프트에 부품 블록이 없어야 함(회귀0)."""
from shopping_shorts import script_generate as SG
from shopping_shorts import comment_gen


class _FakeModels:
    def __init__(self, box):
        self._box = box

    def generate_content(self, model, contents, config):
        self._box["prompt"] = contents

        class _R:
            text = '{"drafts": []}'
        return _R()


def _patch_gemini(monkeypatch, box):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))

    class _FakeClient:
        models = _FakeModels(box)
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda key: _FakeClient())


def test_bank_context_injected_into_gen_prompt(monkeypatch):
    box = {}
    _patch_gemini(monkeypatch, box)
    SG.generate_variations({}, "원본대본", {}, {},
                           bank_context="[승인된 부품]\n· 훅: 이거대박훅")
    assert "이거대박훅" in box["prompt"]


def test_empty_bank_context_leaves_prompt_clean(monkeypatch):
    box = {}
    _patch_gemini(monkeypatch, box)
    SG.generate_variations({}, "원본대본", {}, {})
    assert "승인된 부품" not in box["prompt"]


def test_bank_context_injected_into_mix_prompt(monkeypatch):
    box = {}
    # generate_mix는 _generate_drafts(_call_json 경로) 사용 → 그걸 직접 포착
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])  # len<2 가드 통과 후 실제 호출
    monkeypatch.setattr(SG, "_generate_drafts", lambda prompt: box.setdefault("prompt", prompt) and [])
    SG.generate_mix([{"name": "a", "full_text": "대본A"}, {"name": "b", "full_text": "대본B"}],
                    bank_context="[승인된 부품]\n· CTA: 댓글남겨요")
    assert "댓글남겨요" in box["prompt"]
