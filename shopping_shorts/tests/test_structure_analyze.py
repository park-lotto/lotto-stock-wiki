import json

from shopping_shorts import structure_analyze, comment_gen


def _wire(mp, text):
    mp.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    mp.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    def gen(model, contents, config):
        return type("R", (), {"text": text})()
    models = type("M", (), {"generate_content": staticmethod(gen)})()
    mp.setattr(comment_gen, "_client_for_key", lambda key: type("C", (), {"models": models})())


def test_analyze_ok(monkeypatch):
    _wire(monkeypatch, json.dumps({"hook_type": "경고형", "hook_line": "생선 구울 때 기름 절대 안 돼요",
                                   "beats": [{"label": "훅", "desc": "경고", "approx_sec": "0-2"}],
                                   "devices": ["권위자인용"], "one_line_why": "손실회피 훅"}))
    out = structure_analyze.analyze_structure("생선 구울 때 기름 절대 안 돼요 ...")
    assert out["hook_type"] == "경고형"
    assert out["beats"][0]["label"] == "훅"


def test_analyze_no_keys(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [])
    assert structure_analyze.analyze_structure("x") == {}


def test_analyze_empty_text_is_noop(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    assert structure_analyze.analyze_structure("   ") == {}


def test_analyze_bad_json(monkeypatch):
    _wire(monkeypatch, "not json")
    assert structure_analyze.analyze_structure("x") == {}
