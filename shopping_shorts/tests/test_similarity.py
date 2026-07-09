import pytest
from shopping_shorts import similarity


class _FakeThumbResp:
    content = b"fake-thumb-bytes"


def test_score_candidate_parses_gemini_score(monkeypatch, tmp_path):
    monkeypatch.setattr(similarity, "SHORTS_GEMINI_KEYS", ["fake-key"])
    monkeypatch.setattr(similarity.requests, "get", lambda url, timeout: _FakeThumbResp())
    frame = tmp_path / "f1.jpg"
    frame.write_bytes(b"jpg")

    class FakeClient:
        class models:
            @staticmethod
            def generate_content(**kw):
                class R: text = '{"score": 0.82, "reason": "같은 제품 병 모양"}'
                return R()

    monkeypatch.setattr(similarity, "_client_for_key", lambda key: FakeClient())

    score = similarity.score_candidate([frame], "https://example.com/candidate_thumb.jpg")
    assert score == 0.82


def test_score_candidate_on_error_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(similarity, "SHORTS_GEMINI_KEYS", ["fake-key"])
    monkeypatch.setattr(similarity.requests, "get", lambda url, timeout: _FakeThumbResp())
    frame = tmp_path / "f1.jpg"
    frame.write_bytes(b"jpg")

    class FakeClient:
        class models:
            @staticmethod
            def generate_content(**kw):
                raise RuntimeError("quota")

    monkeypatch.setattr(similarity, "_client_for_key", lambda key: FakeClient())

    assert similarity.score_candidate([frame], "https://example.com/x.jpg") is None


def test_score_candidate_no_keys_returns_none(monkeypatch, tmp_path):
    """SHORTS_GEMINI_KEYS가 비어있으면(전용 풀 소진) 네트워크 호출 없이 바로 None."""
    monkeypatch.setattr(similarity, "SHORTS_GEMINI_KEYS", [])
    frame = tmp_path / "f1.jpg"
    frame.write_bytes(b"jpg")
    assert similarity.score_candidate([frame], "https://example.com/x.jpg") is None
