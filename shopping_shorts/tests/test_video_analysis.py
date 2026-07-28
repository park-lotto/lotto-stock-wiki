import pytest
from shopping_shorts import video_analysis, comment_gen


@pytest.fixture(autouse=True)
def isolate_shorts_gemini_state(monkeypatch, tmp_path):
    """모든 테스트에서 실제 data/shorts_gemini_state.json을 절대 건드리지 않는다."""
    monkeypatch.setattr(comment_gen, "_STATE_PATH", tmp_path / "shorts_gemini_state.json")


class FakeFileObj:
    def __init__(self, name, state):
        self.name = name
        self.state = type("S", (), {"name": state})()


def test_analyze_video_uploads_polls_and_parses(monkeypatch, tmp_path):
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"fake")

    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["fake-key"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["fake-key"])

    states = iter(["PROCESSING", "ACTIVE"])  # 첫 폴링은 처리중, 두번째는 완료
    deleted = []

    class FakeFiles:
        def upload(self, file, config):
            return FakeFileObj("files/abc", "PROCESSING")
        def get(self, name):
            return FakeFileObj(name, next(states))
        def delete(self, name):
            deleted.append(name)

    class FakeModels:
        def generate_content(self, **kw):
            class R: text = '{"keywords":{"ko":["바닥 청소"],"en":["floor cleaner"],"zh":["地板清洁"],"ja":["床掃除"],"ru":["уборка полов"]},"category":"생활용품/홈케어"}'
            return R()

    class FakeClient:
        files = FakeFiles()
        models = FakeModels()

    monkeypatch.setattr(video_analysis, "_client_for_key", lambda key: FakeClient())
    monkeypatch.setattr(video_analysis.time, "sleep", lambda s: None)

    result = video_analysis.analyze_video(video_path, caption="여름 바닥 청소")

    assert result["keywords"]["ko"] == ["바닥 청소"]
    assert result["category"] == "생활용품/홈케어"
    assert deleted == ["files/abc"]  # 업로드한 파일 정리됐는지


def test_analyze_video_no_keys_raises(monkeypatch, tmp_path):
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"fake")
    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", [])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [])
    with pytest.raises(RuntimeError, match="SHORTS_GEMINI_KEY"):
        video_analysis.analyze_video(video_path, caption="")


def test_analyze_video_failed_processing_returns_empty(monkeypatch, tmp_path):
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"fake")
    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["fake-key"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["fake-key"])

    class FakeFiles:
        def upload(self, file, config):
            return FakeFileObj("files/abc", "PROCESSING")
        def get(self, name):
            return FakeFileObj(name, "FAILED")
        def delete(self, name):
            pass

    class FakeClient:
        files = FakeFiles()

    monkeypatch.setattr(video_analysis, "_client_for_key", lambda key: FakeClient())
    monkeypatch.setattr(video_analysis.time, "sleep", lambda s: None)

    result = video_analysis.analyze_video(video_path, caption="")
    assert result == {"keywords": {"ko": [], "en": [], "zh": [], "ja": [], "ru": []}, "category": ""}


def test_analyze_video_rotates_to_next_key_on_daily_exhaustion(monkeypatch, tmp_path):
    """첫 번째 키가 일일 한도 소진 에러를 던지면 두 번째 키로 로테이션."""
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"fake")

    calls = []

    class FakeFiles:
        def upload(self, file, config):
            return FakeFileObj("files/abc", "ACTIVE")
        def get(self, name):
            return FakeFileObj(name, "ACTIVE")
        def delete(self, name):
            pass

    class FakeModels:
        def __init__(self, key):
            self.key = key
        def generate_content(self, **kw):
            calls.append(self.key)
            if self.key == "key1":
                raise RuntimeError("429 RESOURCE_EXHAUSTED PerDay limit reached")
            class FakeResp:
                text = '{"keywords":{"ko":["test"],"en":["test"],"zh":["test"]},"category":"test"}'
            return FakeResp()

    class FakeClient:
        def __init__(self, key):
            self.files = FakeFiles()
            self.models = FakeModels(key)

    def fake_client_for_key(key):
        return FakeClient(key)

    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["key1", "key2"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["key1", "key2"])
    monkeypatch.setattr(video_analysis, "_client_for_key", fake_client_for_key)
    monkeypatch.setattr(video_analysis.time, "sleep", lambda s: None)

    result = video_analysis.analyze_video(video_path, caption="test")

    assert result["keywords"]["ko"] == ["test"]
    assert calls == ["key1", "key2"]
    # key1은 영구 소진 처리되어 다음 호출에서도 건너뛴다.
    assert comment_gen._live_key_indices() == [1]


def test_analyze_video_rotates_to_next_key_on_account_disabled(monkeypatch, tmp_path):
    """키의 서비스 계정 자체가 비활성화된 경우(401 UNAUTHENTICATED)도 일일
    소진과 동일하게 다음 키로 로테이션한다(2026-07-10, 새 키 추가 후에도
    계속 빈 결과가 나오던 원인 — 이 에러는 기존 분류에 안 걸려서 죽은 키만
    계속 재시도하고 있었음)."""
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"fake")

    calls = []

    class FakeFiles:
        def upload(self, file, config):
            return FakeFileObj("files/abc", "ACTIVE")
        def get(self, name):
            return FakeFileObj(name, "ACTIVE")
        def delete(self, name):
            pass

    class FakeModels:
        def __init__(self, key):
            self.key = key
        def generate_content(self, **kw):
            calls.append(self.key)
            if self.key == "key1":
                raise RuntimeError(
                    "401 UNAUTHENTICATED. The bound service account is deleted "
                    "or disabled. {'reason': 'ACCOUNT_STATE_INVALID'}"
                )
            class FakeResp:
                text = '{"keywords":{"ko":["test"],"en":["test"],"zh":["test"],"ja":["test"],"ru":["test"]},"category":"test"}'
            return FakeResp()

    class FakeClient:
        def __init__(self, key):
            self.files = FakeFiles()
            self.models = FakeModels(key)

    def fake_client_for_key(key):
        return FakeClient(key)

    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["key1", "key2"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["key1", "key2"])
    monkeypatch.setattr(video_analysis, "_client_for_key", fake_client_for_key)
    monkeypatch.setattr(video_analysis.time, "sleep", lambda s: None)

    result = video_analysis.analyze_video(video_path, caption="test")

    assert result["keywords"]["ko"] == ["test"]
    assert calls == ["key1", "key2"]
    assert comment_gen._live_key_indices() == [1]


def test_translate_keyword_returns_5langs(monkeypatch, tmp_path):
    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["fake-key"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["fake-key"])

    class FakeModels:
        def generate_content(self, **kw):
            class R:
                text = '{"en":"Balloon Potato","zh":"气球土豆","ja":"バルーンポテト","ru":"Картофельный шар"}'
            return R()

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr(video_analysis, "_client_for_key", lambda key: FakeClient())

    result = video_analysis.translate_keyword("풍선감자")

    assert result == {
        "ko": "풍선감자", "en": "Balloon Potato", "zh": "气球土豆",
        "ja": "バルーンポテト", "ru": "Картофельный шар",
    }


def test_translate_keyword_empty_keyword_returns_ko_only(monkeypatch):
    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["fake-key"])
    result = video_analysis.translate_keyword("")
    assert result == {"ko": "", "en": "", "zh": "", "ja": "", "ru": ""}


def test_translate_keyword_no_keys_returns_ko_only(monkeypatch):
    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", [])
    result = video_analysis.translate_keyword("풍선감자")
    assert result == {"ko": "풍선감자", "en": "", "zh": "", "ja": "", "ru": ""}


def test_analyze_video_all_keys_exhausted_returns_empty(monkeypatch, tmp_path):
    """모든 키가 소진되면 공허한 결과를 반환."""
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"fake")

    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["key1"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["key1"])
    # key1을 미리 소진 상태로 마킹
    comment_gen._mark_key_exhausted(0)

    def fail(*a, **kw):
        raise AssertionError("소진된 키로는 호출하면 안 된다")

    monkeypatch.setattr(video_analysis, "_client_for_key", fail)

    result = video_analysis.analyze_video(video_path, caption="test")
    assert result == {"keywords": {"ko": [], "en": [], "zh": [], "ja": [], "ru": []}, "category": ""}


def test_text_level_vision_returns_level(monkeypatch):
    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["fake-key"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["fake-key"])

    class FakeModels:
        def generate_content(self, **kw):
            class R: text = '{"text_level": "heavy"}'
            return R()

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr(video_analysis, "_client_for_key", lambda key: FakeClient())

    assert video_analysis.text_level_vision(b"fakeimg") == {"text_level": "heavy"}


def test_text_level_vision_no_keys_returns_empty(monkeypatch):
    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", [])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [])
    assert video_analysis.text_level_vision(b"fakeimg") == {}


def test_text_level_vision_no_image_returns_empty(monkeypatch):
    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["fake-key"])
    assert video_analysis.text_level_vision(None) == {}


def test_text_level_vision_invalid_level_returns_empty(monkeypatch):
    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["fake-key"])
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["fake-key"])

    class FakeModels:
        def generate_content(self, **kw):
            class R: text = '{"text_level": "unknown"}'
            return R()

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr(video_analysis, "_client_for_key", lambda key: FakeClient())
    assert video_analysis.text_level_vision(b"img") == {}


def test_fetch_thumb_bytes_uses_rednote_referer_for_xhs_cdn(monkeypatch):
    captured = {}

    class FakeResp:
        content = b"imgdata"

        def raise_for_status(self):
            pass

    def fake_get(url, timeout, headers):
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr("requests.get", fake_get)

    result = video_analysis.fetch_thumb_bytes("http://sns-webpic-qc.xhscdn.com/foo.jpg")
    assert result == b"imgdata"
    assert captured["headers"]["Referer"] == "https://www.rednote.com/"


def test_fetch_thumb_bytes_uses_instagram_referer_by_default(monkeypatch):
    captured = {}

    class FakeResp:
        content = b"imgdata"

        def raise_for_status(self):
            pass

    def fake_get(url, timeout, headers):
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr("requests.get", fake_get)

    video_analysis.fetch_thumb_bytes("http://scontent.cdninstagram.com/foo.jpg")
    assert captured["headers"]["Referer"] == "https://www.instagram.com/"
