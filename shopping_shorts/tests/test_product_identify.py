import pytest
from shopping_shorts import comment_gen, product_identify


@pytest.fixture(autouse=True)
def isolate_shorts_gemini_state(monkeypatch, tmp_path):
    monkeypatch.setattr(comment_gen, "_STATE_PATH", tmp_path / "shorts_gemini_state.json")


class _FakeResponse:
    def __init__(self, payload, status_ok=True):
        self._payload = payload
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            import requests
            raise requests.HTTPError("boom")

    def json(self):
        return self._payload


def test_lens_matches_returns_normalized(monkeypatch):
    monkeypatch.setattr(product_identify, "SERPAPI_KEYS", ["fake-key"])
    monkeypatch.setattr(product_identify, "SERPAPI_KEY", "fake-key")

    def fake_get(url, params=None, timeout=None):
        assert params["engine"] == "google_lens"
        return _FakeResponse({"visual_matches": [
            {"source": "Amazon", "title": "reMarkable Paper Pro"},
            {"source": "eBay", "title": "no source but has title"},
        ]})
    monkeypatch.setattr(product_identify.requests, "get", fake_get)

    result = product_identify._lens_matches("https://x.com/frame.jpg")
    assert result == [
        {"source": "Amazon", "title": "reMarkable Paper Pro"},
        {"source": "eBay", "title": "no source but has title"},
    ]


def test_lens_matches_request_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(product_identify, "SERPAPI_KEYS", ["fake-key"])
    monkeypatch.setattr(product_identify, "SERPAPI_KEY", "fake-key")

    def fake_get(url, params=None, timeout=None):
        return _FakeResponse({}, status_ok=False)
    monkeypatch.setattr(product_identify.requests, "get", fake_get)

    assert product_identify._lens_matches("https://x.com/frame.jpg") == []


def test_lens_matches_no_key_returns_empty(monkeypatch):
    monkeypatch.setattr(product_identify, "SERPAPI_KEYS", [])
    monkeypatch.setattr(product_identify, "SERPAPI_KEY", "")
    assert product_identify._lens_matches("https://x.com/frame.jpg") == []


def test_identify_product_no_serpapi_key_returns_empty(monkeypatch):
    monkeypatch.setattr(product_identify, "SERPAPI_KEYS", [])
    monkeypatch.setattr(product_identify, "SERPAPI_KEY", "")
    assert product_identify.identify_product(["https://x.com/f1.jpg"]) == ""


def test_identify_product_no_frames_returns_empty(monkeypatch):
    monkeypatch.setattr(product_identify, "SERPAPI_KEYS", ["fake-key"])
    monkeypatch.setattr(product_identify, "SERPAPI_KEY", "fake-key")
    assert product_identify.identify_product([]) == ""


def test_identify_product_no_matches_skips_gemini_call(monkeypatch):
    """모든 프레임이 매칭 없으면 Gemini 호출 없이 빈 문자열(비용 절약)."""
    monkeypatch.setattr(product_identify, "SERPAPI_KEYS", ["fake-key"])
    monkeypatch.setattr(product_identify, "SERPAPI_KEY", "fake-key")
    monkeypatch.setattr(product_identify, "_lens_matches", lambda url, **kw: [])

    called = []
    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: called.append(1) or (None, None))

    result = product_identify.identify_product(["https://x.com/f1.jpg", "https://x.com/f2.jpg"])
    assert result == ""
    assert called == []


def test_identify_product_aggregates_frames_and_returns_name(monkeypatch):
    monkeypatch.setattr(product_identify, "SERPAPI_KEYS", ["fake-key"])
    monkeypatch.setattr(product_identify, "SERPAPI_KEY", "fake-key")
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["fake-gemini-key"])
    monkeypatch.setattr(product_identify, "SHORTS_GEMINI_KEYS", ["fake-gemini-key"])

    def fake_lens_matches(url, **kw):
        if "f1" in url:
            return [{"source": "Amazon", "title": "reMarkable Paper Pro e-ink tablet"}]
        if "f2" in url:
            return []  # 배경 소품 프레임 — 매칭 없음
        return [{"source": "eBay", "title": "reMarkable tablet stylus"}]
    monkeypatch.setattr(product_identify, "_lens_matches", fake_lens_matches)

    captured = {}
    class FakeModels:
        def generate_content(self, **kw):
            captured["prompt"] = kw["contents"]
            class R: text = '{"product_name": "reMarkable Paper Pro"}'
            return R()
    class FakeClient:
        models = FakeModels()
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda key: FakeClient())

    result = product_identify.identify_product(
        ["https://x.com/f1.jpg", "https://x.com/f2.jpg", "https://x.com/f3.jpg"],
        category="가전/디지털", caption="전자노트 리뷰",
    )

    assert result == "reMarkable Paper Pro"
    assert "프레임1" in captured["prompt"]
    assert "프레임3" in captured["prompt"]
    assert "프레임2" not in captured["prompt"]  # 매칭 없는 프레임은 프롬프트에서 제외


def test_identify_product_no_gemini_keys_returns_empty(monkeypatch):
    monkeypatch.setattr(product_identify, "SERPAPI_KEYS", ["fake-key"])
    monkeypatch.setattr(product_identify, "SERPAPI_KEY", "fake-key")
    monkeypatch.setattr(product_identify, "SHORTS_GEMINI_KEYS", [])
    monkeypatch.setattr(product_identify, "_lens_matches",
                         lambda url, **kw: [{"source": "s", "title": "t"}])

    assert product_identify.identify_product(["https://x.com/f1.jpg"]) == ""


def test_prompt_main_product_vs_background_prop_guard():
    """배경 소품·동물에 낚여 주 제품을 오인하는 것을 막는 지시가 프롬프트에 있는지(2026-07-29 실사고)."""
    p = product_identify._PROMPT
    assert "배경 소품" in p
    assert "동물" in p
