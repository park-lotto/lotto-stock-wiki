import pytest
from shopping_shorts import comment_gen


@pytest.fixture(autouse=True)
def isolate_shorts_gemini_state(monkeypatch, tmp_path):
    """모든 테스트에서 실제 data/shorts_gemini_state.json을 절대 건드리지 않는다."""
    monkeypatch.setattr(comment_gen, "_STATE_PATH", tmp_path / "shorts_gemini_state.json")


def test_build_prompt_includes_caption_and_category():
    p = comment_gen.build_prompt("좁은 원룸 수납 꿀팁 대공개", "오후살림", "생활용품")
    assert "좁은 원룸 수납 꿀팁" in p
    assert "생활용품" in p
    assert "3" in p

def test_parse_response_valid_json():
    raw = '["이거 어디 제품이에요?", "저도 원룸인데 참고돼요", "수납 꿀팁 감사해요"]'
    out = comment_gen.parse_response(raw)
    assert out == ["이거 어디 제품이에요?", "저도 원룸인데 참고돼요", "수납 꿀팁 감사해요"]

def test_parse_response_object_with_comments_key():
    raw = '{"comments": ["a", "b", "c"]}'
    assert comment_gen.parse_response(raw) == ["a", "b", "c"]

def test_parse_response_bad_returns_empty():
    assert comment_gen.parse_response("not json") == []
    assert comment_gen.parse_response("") == []

def test_generate_uses_client(monkeypatch):
    class FakeResp:
        text = '["댓글1", "댓글2", "댓글3"]'
    class FakeModels:
        def generate_content(self, **kw): return FakeResp()
    class FakeClient:
        models = FakeModels()
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["fake-key"])
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda key: FakeClient())
    out = comment_gen.generate("캡션텍스트", "채널", "뷰티")
    assert out == ["댓글1", "댓글2", "댓글3"]

def test_generate_empty_caption_still_tries(monkeypatch):
    class FakeResp:
        text = '["안녕하세요 잘 보고가요", "영상 좋네요", "팔로우하고가요"]'
    class FakeClient:
        class models:
            @staticmethod
            def generate_content(**kw): return FakeResp()
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["fake-key"])
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda key: FakeClient())
    out = comment_gen.generate("", "채널명", "기타")
    assert len(out) == 3

def test_generate_rotates_to_next_key_on_daily_exhaustion(monkeypatch):
    calls = []
    class FakeClient:
        def __init__(self, key): self.key = key
        class models:
            pass
    def fake_client_for_key(key):
        c = FakeClient(key)
        def generate_content(**kw):
            calls.append(key)
            if key == "key1":
                raise RuntimeError("429 RESOURCE_EXHAUSTED PerDay limit reached")
            class FakeResp:
                text = '["a", "b", "c"]'
            return FakeResp()
        c.models = type("M", (), {"generate_content": staticmethod(generate_content)})()
        return c
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["key1", "key2"])
    monkeypatch.setattr(comment_gen, "_client_for_key", fake_client_for_key)
    out = comment_gen.generate("캡션", "채널", "기타")
    assert out == ["a", "b", "c"]
    assert calls == ["key1", "key2"]
    # key1은 영구 소진 처리되어 다음 호출에서도 건너뛴다.
    assert comment_gen._live_key_indices() == [1]

def test_generate_no_keys_raises(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [])
    with pytest.raises(RuntimeError, match="SHORTS_GEMINI_KEY"):
        comment_gen.generate("캡션", "채널", "기타")

def test_generate_all_keys_exhausted_returns_empty(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["key1"])
    comment_gen._mark_key_exhausted(0)
    def fail(*a, **kw):
        raise AssertionError("소진된 키로는 호출하면 안 된다")
    monkeypatch.setattr(comment_gen, "_client_for_key", fail)
    assert comment_gen.generate("캡션", "채널", "기타") == []
