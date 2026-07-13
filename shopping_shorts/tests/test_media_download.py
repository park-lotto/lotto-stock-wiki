from shopping_shorts import media_download as md


def test_route_instagram(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(md, "_download_instagram", lambda url, d: called.setdefault("ig", url) or str(tmp_path / "ig.mp4"))
    monkeypatch.setattr(md, "_download_ytdlp", lambda url, d: (_ for _ in ()).throw(AssertionError("ytdlp 호출됨")))
    out = md.download_any("https://www.instagram.com/reel/ABC/", str(tmp_path))
    assert called["ig"].endswith("/reel/ABC/")


def test_route_youtube(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(md, "_download_ytdlp", lambda url, d: called.setdefault("yt", url) or str(tmp_path / "yt.mp4"))
    md.download_any("https://www.youtube.com/watch?v=vid1", str(tmp_path))
    assert "youtube.com" in called["yt"]


def test_route_tiktok(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(md, "_download_ytdlp", lambda url, d: called.setdefault("tt", url) or str(tmp_path / "tt.mp4"))
    md.download_any("https://www.tiktok.com/@u/video/123", str(tmp_path))
    assert "tiktok.com" in called["tt"]
