import tempfile
from pathlib import Path
from shopping_shorts import tts


def test_synthesize_without_key_writes_mock(monkeypatch):
    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "")
    out = Path(tempfile.mkdtemp()) / "b.mp3"
    ret = tts.synthesize_tts("안녕하세요", str(out))
    assert ret == str(out)
    assert out.exists() and out.stat().st_size > 0  # mock 무음이라도 파일 존재


def test_synthesize_with_key_calls_api(monkeypatch):
    calls = {}

    class FakeResp:
        status_code = 200
        content = b"ID3fakebytes"
        def raise_for_status(self): pass

    def fake_post(url, **kw):
        calls["url"] = url
        calls["json"] = kw.get("json")
        calls["headers"] = kw.get("headers")
        return FakeResp()

    monkeypatch.setattr(tts.config, "ELEVENLABS_API_KEY", "sk-test")
    monkeypatch.setattr(tts.config, "ELEVENLABS_VOICE_ID", "voiceX")
    monkeypatch.setattr(tts.requests, "post", fake_post)

    out = Path(tempfile.mkdtemp()) / "b.mp3"
    tts.synthesize_tts("테스트 문장", str(out))
    assert "voiceX" in calls["url"]
    assert calls["json"]["text"] == "테스트 문장"
    assert calls["headers"]["xi-api-key"] == "sk-test"
    assert out.read_bytes() == b"ID3fakebytes"
