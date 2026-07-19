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


def test_direct_mp4_downloaded_without_ytdlp(monkeypatch, tmp_path):
    # 샤오홍슈 play_url(직접 mp4/xhscdn)은 yt-dlp 안 거치고 그대로 HTTP 다운로드(비용 0).
    import shopping_shorts.frame_extract as frame_extract
    monkeypatch.setattr(frame_extract, "download_video", lambda video_url, dest: tmp_path / "xhs.mp4")

    def _boom(*a, **k):
        raise AssertionError("yt-dlp를 타면 안 된다(직접 mp4)")
    monkeypatch.setattr(md, "_download_ytdlp", _boom)

    path, caption = md.download_any("https://sns-video-hw.xhscdn.com/stream/1/abc.mp4?token=x", str(tmp_path))
    assert path.endswith("xhs.mp4")
    assert caption == ""


def test_is_direct_video_page_vs_file():
    assert md._is_direct_video("https://sns-video-hw.xhscdn.com/a.mp4?t=1")
    assert md._is_direct_video("https://v.zjcdn.com/abc")
    # 페이지 URL은 직접영상 아님 → yt-dlp 경로로 가야 한다
    assert not md._is_direct_video("https://www.rednote.com/search_result/689ea3ac")
    assert not md._is_direct_video("https://www.xiaohongshu.com/discovery/item/abc?xsec_token=y")


def test_rednote_page_routed_to_ytdlp(monkeypatch, tmp_path):
    # rednote.com 페이지는 지원목록에 들어가 yt-dlp로 라우팅(더는 '지원하지 않는 URL' 아님).
    called = {}
    monkeypatch.setattr(md, "_download_ytdlp", lambda url, d: (called.setdefault("u", url), "x.mp4")[1:] and (url, ""))
    path, caption = md.download_any("https://www.rednote.com/explore/abc", str(tmp_path))
    assert "rednote.com" in called["u"]
