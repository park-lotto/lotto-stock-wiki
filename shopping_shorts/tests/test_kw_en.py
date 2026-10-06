"""관제 151 — 인스타 검색용 영어 검색어(최대 3단어) 판단과 /api/lens/kw/en 라우트."""
import json
from types import SimpleNamespace

from shopping_shorts import video_analysis as va


def test_clean_en_term_caps_at_three_words():
    # 사장님 로그인 화면 실측: 4단어는 결과 0, 3단어까지 결과가 나온다.
    assert va._clean_en_term("amazon range hood") == "amazon range hood"
    assert va._clean_en_term("Amazon Countertop") == "amazon countertop"
    assert va._clean_en_term("amazon kitchen range hood") == ""
    assert va._clean_en_term("#amazonfinds") == "amazonfinds"
    assert va._clean_en_term("휴대용 레인지후드") == ""          # 영어만
    assert va._clean_en_term("  ") == ""


class _FakeModels:
    def __init__(self, payload):
        self.payload = payload

    def generate_content(self, **kw):
        return SimpleNamespace(text=json.dumps(self.payload))


def _patch_model(monkeypatch, payload):
    monkeypatch.setattr(va, "SHORTS_GEMINI_KEYS", ["k"])
    monkeypatch.setattr(va.comment_gen, "_next_live_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(va, "_client_for_key", lambda key: SimpleNamespace(models=_FakeModels(payload)))


def test_english_search_terms_filters_long_and_duplicates(monkeypatch):
    _patch_model(monkeypatch, {"main": "Amazon Range Hood",
                               "related": ["amazon range hood", "amazon kitchen range hood",
                                           "portable vent hood", "주방 후드", "cooking odor remover"]})
    r = va.english_search_terms("This portable range hood from Amazon…", kind="caption")
    assert r["main"] == "amazon range hood"
    assert r["related"] == ["portable vent hood", "cooking odor remover"]


def test_english_query_falls_back_to_input_when_model_main_bad(monkeypatch):
    _patch_model(monkeypatch, {"main": "", "related": ["kitchen gadgets"]})
    r = va.english_search_terms("Life hacks gadgets", kind="query")
    assert r["main"] == "life hacks gadgets"


def test_route_returns_terms(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    client = TestClient(app_mod.app)
    monkeypatch.setattr(app_mod.video_analysis, "english_search_terms",
                        lambda text, kind: {"main": "portable range hood", "related": ["desktop range hood"]})
    res = client.post("/api/lens/kw/en", json={"text": "휴대용 레인지후드", "kind": "query"})
    assert res.status_code == 200
    d = res.json()
    assert d["ok"] and d["main"] == "portable range hood" and d["related"] == ["desktop range hood"]


def test_multi_route_and_en_cap(monkeypatch, tmp_path):
    """비슷한 검색어 5개 언어 — expand_search_keywords 결과를 그대로 싣고, 영어는 3단어 상한을 넘으면 비운다."""
    from fastapi.testclient import TestClient
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    _patch_model(monkeypatch, {"candidates": [
        {"ko": "자석 양념통", "zh": "磁吸调料罐", "en": "magnetic spice tins", "ja": "", "ru": ""},
        {"ko": "주방 수납", "zh": "厨房收纳", "en": "kitchen cabinet storage ideas", "ja": "収納", "ru": "хранение"}]})
    cands = va.expand_search_keywords("자석 양념통", n=5)
    assert cands[0]["en"] == "magnetic spice tins"
    assert cands[1]["en"] == ""                       # 4단어 → 비움
    monkeypatch.setattr(app_mod, "expand_search_keywords", lambda text, n=5: cands)
    d = TestClient(app_mod.app).post("/api/lens/kw/multi", json={"text": "자석 양념통"}).json()
    assert d["ok"] and [c["ko"] for c in d["candidates"]] == ["자석 양념통", "주방 수납"]
