import json

from shopping_shorts import script_generate, comment_gen

_STRUCT = {"characters": [{"who": "농원 언니", "role": "정보원"}], "twist": "관상용→가전",
           "development": "문제→해결", "hook": "언니네 집은 왜 안 습해?", "appeal": "편리함",
           "tone": "친근한 수다체"}


def _wire(mp, text):
    mp.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    mp.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    def gen(model, contents, config):
        return type("R", (), {"text": text})()
    models = type("M", (), {"generate_content": staticmethod(gen)})()
    mp.setattr(comment_gen, "_client_for_key", lambda key: type("C", (), {"models": models})())


def test_generate_ok(monkeypatch):
    _wire(monkeypatch, json.dumps({"drafts": [{"hook": "h", "script": "s", "applied": "a"}]}))
    out = script_generate.generate_variations(_STRUCT, "원본 대본", {"characters": True}, "A")
    assert out[0]["script"] == "s"


def test_generate_no_keys(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [])
    assert script_generate.generate_variations(_STRUCT, "t", {}, "A") == []


def test_generate_empty_text_is_noop(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    assert script_generate.generate_variations(_STRUCT, "   ", {}, "A") == []


def test_generate_bad_json(monkeypatch):
    _wire(monkeypatch, "not json")
    assert script_generate.generate_variations(_STRUCT, "t", {}, "A") == []


def test_elem_lines_keep_vs_vary():
    lines = script_generate._elem_lines(_STRUCT, {"characters": True, "twist": False})
    assert "유지" in lines and "변형" in lines
    assert "농원 언니" in lines  # characters를 사람이 읽을 형태로 펼침
