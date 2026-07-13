from shopping_shorts import media_download as md


def test_route_instagram(monkeypatch, tmp_path):
    called = {}

    def fake_ig(url, d):
        called["ig"] = url
        return str(tmp_path / "ig.mp4"), "캡션"
    monkeypatch.setattr(md, "_download_instagram", fake_ig)
    monkeypatch.setattr(md, "_download_ytdlp", lambda url, d: (_ for _ in ()).throw(AssertionError("ytdlp 호출됨")))
    path, caption = md.download_any("https://www.instagram.com/reel/ABC/", str(tmp_path))
    assert called["ig"].endswith("/reel/ABC/")
    assert path.endswith("ig.mp4")
    assert caption == "캡션"


def test_route_youtube(monkeypatch, tmp_path):
    called = {}

    def fake_yt(url, d):
        called["yt"] = url
        return str(tmp_path / "yt.mp4"), ""
    monkeypatch.setattr(md, "_download_ytdlp", fake_yt)
    path, caption = md.download_any("https://www.youtube.com/watch?v=vid1", str(tmp_path))
    assert "youtube.com" in called["yt"]
    assert caption == ""


def test_route_tiktok(monkeypatch, tmp_path):
    called = {}

    def fake_tt(url, d):
        called["tt"] = url
        return str(tmp_path / "tt.mp4"), ""
    monkeypatch.setattr(md, "_download_ytdlp", fake_tt)
    path, caption = md.download_any("https://www.tiktok.com/@u/video/123", str(tmp_path))
    assert "tiktok.com" in called["tt"]
    assert caption == ""


def test_download_instagram_returns_caption_from_raw(monkeypatch, tmp_path):
    # _download_instagram 자체가 fetch_single_reel의 caption 필드를 그대로 넘겨야 한다
    # (Instagram 믹스 캡션 회귀 수정 — 최종리뷰 IMPORTANT).
    import shopping_shorts.apify_client as apify_client
    import shopping_shorts.frame_extract as frame_extract
    monkeypatch.setattr(apify_client, "fetch_single_reel", lambda url: {"videoUrl": "http://cdn/x.mp4", "caption": "원본 캡션"})
    monkeypatch.setattr(frame_extract, "download_video", lambda video_url, dest: tmp_path / "ig.mp4")

    path, caption = md._download_instagram("https://www.instagram.com/reel/ABC/", str(tmp_path))
    assert caption == "원본 캡션"


def test_download_instagram_missing_caption_defaults_empty(monkeypatch, tmp_path):
    import shopping_shorts.apify_client as apify_client
    import shopping_shorts.frame_extract as frame_extract
    monkeypatch.setattr(apify_client, "fetch_single_reel", lambda url: {"videoUrl": "http://cdn/x.mp4"})
    monkeypatch.setattr(frame_extract, "download_video", lambda video_url, dest: tmp_path / "ig.mp4")

    path, caption = md._download_instagram("https://www.instagram.com/reel/ABC/", str(tmp_path))
    assert caption == ""
