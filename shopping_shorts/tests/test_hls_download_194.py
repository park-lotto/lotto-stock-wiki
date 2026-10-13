"""관제 194 — HLS 재생목록을 mp4 이름으로 저장하던 결함 + 길이 하나 실패시 전체 비던 결함."""
import inspect
from pathlib import Path
from shopping_shorts import frame_extract, app


def test_m3u8_url_goes_to_ffmpeg(tmp_path, monkeypatch):
    called = {}
    def fake(url, path):
        called["url"] = url; Path(path).write_bytes(b"x" * 20000); return path
    monkeypatch.setattr(frame_extract, "_download_hls", fake)
    p = frame_extract.download_video("https://v1.pinimg.com/videos/a.m3u8?x=1", tmp_path)
    assert called["url"].endswith("a.m3u8?x=1") and p.suffix == ".mp4"


def test_playlist_body_without_m3u8_url_is_converted(tmp_path, monkeypatch):
    class R:
        def raise_for_status(self): pass
        def iter_content(self, chunk_size): yield b"#EXTM3U\n#EXT-X-VERSION:6\n"
    monkeypatch.setattr(frame_extract.requests, "get", lambda *a, **k: R())
    hit = []
    def fake(url, path):
        hit.append(url); Path(path).write_bytes(b"x" * 20000); return path
    monkeypatch.setattr(frame_extract, "_download_hls", fake)
    frame_extract.download_video("https://cdn/x.mp4", tmp_path)
    assert hit == ["https://cdn/x.mp4"]


def test_scene_lab_probe_is_per_source():
    src = inspect.getsource(app.api_mix_scene_lab_data)
    i = src.index("_probe_duration(p)")
    # 길이 재기가 영상마다 따로 try 안에 있어야 한다(하나 실패해도 나머지는 잰다)
    assert "continue" in src[i:i + 300]
