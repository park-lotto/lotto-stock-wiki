import pytest
from shopping_shorts import similarity, comment_gen


@pytest.fixture(autouse=True)
def isolate_shorts_gemini_state(monkeypatch, tmp_path):
    """모든 테스트에서 실제 data/shorts_gemini_state.json을 절대 건드리지 않는다."""
    monkeypatch.setattr(comment_gen, "_STATE_PATH", tmp_path / "shorts_gemini_state.json")


class _FakeThumbResp:
    content = b"fake-thumb-bytes"


def test_score_candidate_parses_gemini_score(monkeypatch, tmp_path):
    monkeypatch.setattr(similarity, "SHORTS_GEMINI_KEYS", ["fake-key"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["fake-key"])
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
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["fake-key"])
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


def test_score_candidate_rotates_to_next_key_on_daily_exhaustion(monkeypatch, tmp_path):
    """첫 번째 키가 일일 한도 소진 에러를 던지면 두 번째 키로 로테이션(2026-07-09,
    최종 리뷰 Finding 3 — 로테이션이 없으면 키[0] 소진 후 keys[1]/[2]가 멀쩡해도
    모든 후보가 영구 "미검증"으로 남았음)."""
    monkeypatch.setattr(similarity, "SHORTS_GEMINI_KEYS", ["key1", "key2"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["key1", "key2"])
    monkeypatch.setattr(similarity.requests, "get", lambda url, timeout: _FakeThumbResp())
    frame = tmp_path / "f1.jpg"
    frame.write_bytes(b"jpg")

    calls = []

    class FakeModels:
        def __init__(self, key):
            self.key = key

        def generate_content(self, **kw):
            calls.append(self.key)
            if self.key == "key1":
                raise RuntimeError("429 RESOURCE_EXHAUSTED PerDay limit reached")
            class R: text = '{"score": 0.9, "reason": "동일 제품"}'
            return R()

    class FakeClient:
        def __init__(self, key):
            self.models = FakeModels(key)

    monkeypatch.setattr(similarity, "_client_for_key", lambda key: FakeClient(key))
    monkeypatch.setattr(similarity.time, "sleep", lambda s: None)

    score = similarity.score_candidate([frame], "https://example.com/candidate_thumb.jpg")

    assert score == 0.9
    assert calls == ["key1", "key2"]
    # key1은 영구 소진 처리되어 다음 호출에서도 건너뛴다.
    assert comment_gen._live_key_indices() == [1]


def test_score_candidate_all_keys_exhausted_returns_none(monkeypatch, tmp_path):
    """모든 키가 이미 소진 상태로 마킹돼 있으면 호출 없이 None."""
    monkeypatch.setattr(similarity, "SHORTS_GEMINI_KEYS", ["key1"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["key1"])
    monkeypatch.setattr(similarity.requests, "get", lambda url, timeout: _FakeThumbResp())
    comment_gen._mark_key_exhausted(0)
    frame = tmp_path / "f1.jpg"
    frame.write_bytes(b"jpg")

    def fail(*a, **kw):
        raise AssertionError("소진된 키로는 호출하면 안 된다")

    monkeypatch.setattr(similarity, "_client_for_key", fail)

    assert similarity.score_candidate([frame], "https://example.com/x.jpg") is None
