from shopping_shorts import comment_gen


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
    monkeypatch.setattr(comment_gen, "_get_client", lambda: FakeClient())
    out = comment_gen.generate("캡션텍스트", "채널", "뷰티")
    assert out == ["댓글1", "댓글2", "댓글3"]

def test_generate_empty_caption_still_tries(monkeypatch):
    class FakeResp:
        text = '["안녕하세요 잘 보고가요", "영상 좋네요", "팔로우하고가요"]'
    class FakeClient:
        class models:
            @staticmethod
            def generate_content(**kw): return FakeResp()
    monkeypatch.setattr(comment_gen, "_get_client", lambda: FakeClient())
    out = comment_gen.generate("", "채널명", "기타")
    assert len(out) == 3
