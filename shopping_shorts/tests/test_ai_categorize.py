import json

from shopping_shorts import ai_categorize, comment_gen


def _fake_client(text):
    def gen(model, contents, config):
        return type("R", (), {"text": text})()
    models = type("M", (), {"generate_content": staticmethod(gen)})()
    return type("C", (), {"models": models})()


def _wire(monkeypatch, text):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda key: _fake_client(text))


def test_reclassify_overrides_keyword(monkeypatch):
    # 잡곡밥 요리영상이 키워드로 '생활용품' 오판 → AI가 캡션 보고 레시피로 교정.
    _wire(monkeypatch, json.dumps({"0": "레시피", "1": "가전"}))
    items = [
        {"name": "홈잇 | 살림템", "caption": "잡곡밥에 물만 넣고 지으면 안 돼요", "category": "생활용품"},
        {"name": "가전왕", "caption": "로봇청소기 언박싱", "category": "가전"},
    ]
    changed = ai_categorize.reclassify(items)
    assert items[0]["category"] == "레시피"
    assert items[1]["category"] == "가전"  # 이미 맞음 → 그대로
    assert changed == 1


def test_reclassify_handles_list_response(monkeypatch):
    # Gemini가 객체 대신 배열로 답해도 순서로 매핑.
    _wire(monkeypatch, json.dumps([{"i": 0, "category": "뷰티"}]))
    items = [{"name": "x", "caption": "세럼 발색 리뷰", "category": "기타"}]
    ai_categorize.reclassify(items)
    assert items[0]["category"] == "뷰티"


def test_reclassify_ignores_invalid_category(monkeypatch):
    _wire(monkeypatch, json.dumps({"0": "존재안함"}))
    items = [{"name": "x", "caption": "y", "category": "레시피"}]
    assert ai_categorize.reclassify(items) == 0
    assert items[0]["category"] == "레시피"  # 이상값이면 키워드 유지


def test_reclassify_no_keys_is_noop(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [])
    items = [{"name": "x", "caption": "y", "category": "기타"}]
    assert ai_categorize.reclassify(items) == 0
    assert items[0]["category"] == "기타"


def test_reclassify_bad_json_is_noop(monkeypatch):
    _wire(monkeypatch, "not json at all")
    items = [{"name": "x", "caption": "y", "category": "생활용품"}]
    assert ai_categorize.reclassify(items) == 0
    assert items[0]["category"] == "생활용품"
