import json
import pytest
from shopping_shorts import comment_gen, element_stats


@pytest.fixture(autouse=True)
def isolate_state(monkeypatch, tmp_path):
    monkeypatch.setattr(comment_gen, "_STATE_PATH", tmp_path / "shorts_gemini_state.json")


def _wire(mp, text):
    mp.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    mp.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    def gen(model, contents, config):
        return type("R", (), {"text": text})()
    models = type("M", (), {"generate_content": staticmethod(gen)})()
    mp.setattr(comment_gen, "_client_for_key", lambda key: type("C", (), {"models": models})())


def test_cluster_returns_categories_when_enough_samples(monkeypatch):
    payload = json.dumps({"categories": [
        {"label": "가족관계", "description": "엄마·언니 등 가족을 등장시킴", "examples": ["엄마가", "언니가"]},
        {"label": "전문가", "description": "직업 전문가를 인용", "examples": ["병원 하는 지인이"]},
    ]})
    _wire(monkeypatch, payload)
    values = [f"엄마가 알려준 {i}" for i in range(25)]
    out = element_stats.cluster_element_values("characters", values)
    assert len(out) == 2
    assert out[0]["label"] == "가족관계"


def test_cluster_returns_empty_when_below_min_samples(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    called = []
    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: called.append(1) or ("k", 0))
    out = element_stats.cluster_element_values("tone", ["친근한 반말"] * 5)
    assert out == []
    assert called == []  # 표본부족이면 Gemini 호출 자체를 안 한다(비용 절약)


def test_cluster_no_keys_returns_empty(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [])
    out = element_stats.cluster_element_values("tone", ["a"] * 25)
    assert out == []


def test_cluster_bad_json_returns_empty(monkeypatch):
    _wire(monkeypatch, "not json")
    out = element_stats.cluster_element_values("tone", ["a"] * 25)
    assert out == []
