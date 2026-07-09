import pytest
from shopping_shorts import video_analysis


class FakeFileObj:
    def __init__(self, name, state):
        self.name = name
        self.state = type("S", (), {"name": state})()


def test_analyze_video_uploads_polls_and_parses(monkeypatch, tmp_path):
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"fake")

    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["fake-key"])

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
            class R: text = '{"keywords":{"ko":["바닥 청소"],"en":["floor cleaner"],"zh":["地板清洁"]},"category":"생활용품/홈케어"}'
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
    with pytest.raises(RuntimeError, match="SHORTS_GEMINI_KEY"):
        video_analysis.analyze_video(video_path, caption="")


def test_analyze_video_failed_processing_returns_empty(monkeypatch, tmp_path):
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"fake")
    monkeypatch.setattr(video_analysis, "SHORTS_GEMINI_KEYS", ["fake-key"])

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
    assert result == {"keywords": {"ko": [], "en": [], "zh": []}, "category": ""}
