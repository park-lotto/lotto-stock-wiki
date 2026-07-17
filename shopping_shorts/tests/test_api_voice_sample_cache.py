"""성우 샘플은 브라우저가 옛것을 계속 들려주면 안 된다.

★2026-07-17 실측으로 드러난 것: 샘플 47개를 새 속도로 재생성·배포했는데 사장님 화면에선
**여전히 옛 소리**가 났다. 캐시를 우회해 재보니 서버는 새것을 주고 있었다(미나 속삭임
브라우저 3.2초 vs 서버 7.1초). 응답에 `cache-control`이 아예 없어(실측 null) 브라우저가
무기한 캐시한 것.

샘플은 **성우를 재튜닝할 때마다 바뀌는 파일**이다. 캐시 헤더가 없으면 사장님은 앞으로도
계속 옛 소리를 듣고 "왜 안 바뀌지"를 반복한다. no-cache로 매번 검증하게 한다
(FileResponse가 etag·last-modified를 붙이므로 안 바뀌었으면 304로 싸게 끝난다).
"""
from fastapi.testclient import TestClient

from shopping_shorts.app import app
from shopping_shorts import voice_presets


def _setup(monkeypatch, tmp_path):
    mp3 = tmp_path / "demo.mp3"
    mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 512)     # mp3 헤더 흉내
    monkeypatch.setattr(voice_presets, "SAMPLES_DIR", tmp_path)
    monkeypatch.setattr(
        "shopping_shorts.app.Store",
        lambda *a, **k: type("S", (), {
            "get_voice_preset": lambda s, pid: {"preset_id": pid, "sample_file": "demo.mp3"},
        })())
    return TestClient(app)


def test_sample_must_not_be_cached_without_revalidation(monkeypatch, tmp_path):
    """재튜닝하면 바뀌는 파일이므로 브라우저가 무기한 들고 있으면 안 된다."""
    r = _setup(monkeypatch, tmp_path).get("/api/voice-presets/kr-mina-whisper/sample")
    assert r.status_code == 200
    cc = (r.headers.get("cache-control") or "").lower()
    assert cc, "cache-control이 없다 — 브라우저가 옛 샘플을 무기한 들려준다(2026-07-17 실사고)"
    assert "no-cache" in cc or "max-age=0" in cc, f"매번 검증하게 해야 한다: {cc!r}"


def test_sample_still_serves_the_bytes(monkeypatch, tmp_path):
    """캐시 막느라 파일 자체가 안 나가면 본말전도다(반대편 봉인)."""
    r = _setup(monkeypatch, tmp_path).get("/api/voice-presets/kr-mina-whisper/sample")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/")
    assert len(r.content) > 100
