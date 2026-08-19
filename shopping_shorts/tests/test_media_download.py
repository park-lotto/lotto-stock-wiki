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
    # rednote.com은 yt-dlp로 라우팅되되 도메인은 xiaohongshu.com으로 정규화된다(yt-dlp가 인식).
    called = {}
    monkeypatch.setattr(md, "_download_ytdlp", lambda url, d: (called.setdefault("u", url), "x.mp4")[1:] and (url, ""))
    path, caption = md.download_any("https://www.rednote.com/explore/abc", str(tmp_path))
    assert "xiaohongshu.com" in called["u"] and "rednote.com" not in called["u"]


def test_rednote_domain_rewritten_to_xiaohongshu_for_ytdlp(monkeypatch, tmp_path):
    # yt-dlp는 rednote.com을 모른다 → xiaohongshu.com으로 정규화해서 넘겨야 한다(토큰·경로 보존).
    seen = {}
    monkeypatch.setattr(md, "_download_ytdlp", lambda url, d: (seen.setdefault("url", url), ("x.mp4", ""))[1])
    md.download_any("https://www.rednote.com/explore/67765717000000000b0146fe?xsec_token=ABC=&xsec_source=", str(tmp_path))
    assert "xiaohongshu.com" in seen["url"]
    assert "rednote.com" not in seen["url"]
    assert "explore/67765717000000000b0146fe" in seen["url"]   # 경로 보존
    assert "xsec_token=ABC=" in seen["url"]                     # 토큰 보존


def test_search_result_path_rewritten_to_explore(monkeypatch, tmp_path):
    # yt-dlp XiaoHongShuIE는 /explore/{id}·/discovery/item/{id}만 매칭(서버 실측) —
    # 검색그리드 노트(/search_result/{id}?xsec_token=…)는 경로만 /explore/로 바꾼다(토큰 보존).
    seen = {}
    monkeypatch.setattr(md, "_download_ytdlp", lambda url, d: (seen.setdefault("url", url), ("x.mp4", ""))[1])
    md.download_any("https://www.rednote.com/search_result/69932477000000001a0279d6?xsec_token=TOK=&xsec_source=pc_search", str(tmp_path))
    assert "/explore/69932477000000001a0279d6" in seen["url"]
    assert "/search_result/" not in seen["url"]
    assert "xsec_token=TOK=" in seen["url"]          # 토큰 보존
    assert "xiaohongshu.com" in seen["url"]           # 도메인 정규화도 함께


# ── 인스타 세션 쿠키(2026-08-03 실사고 DbhC6twy0IA) ───────────────────────
# 무쿠키 yt-dlp에 인스타가 'empty media response'를 주고 Apify 폴백은 17계정 소진 →
# 담기 예열이 통째로 죽었다. 수집기 세션(storage_state)을 cookies.txt로 변환해 태운다.

def test_ig_cookies_converted_from_storage_state(tmp_path, monkeypatch):
    import json as _json
    from shopping_shorts import media_download as md
    sess = tmp_path / "instagram_session.json"
    sess.write_text(_json.dumps({"cookies": [
        {"name": "sessionid", "value": "abc", "domain": ".instagram.com",
         "path": "/", "secure": True, "expires": 1999999999},
    ]}), encoding="utf-8")
    monkeypatch.setattr(md.config, "INSTAGRAM_SESSION_PATH", str(sess))
    args = md._cookies_arg("https://www.instagram.com/reel/XYZ/")
    assert args and args[0] == "--cookies"
    body = open(args[1], encoding="utf-8").read()
    assert "sessionid\tabc" in body and ".instagram.com" in body


def test_ig_cookies_missing_session_falls_back_to_no_cookies(monkeypatch):
    from shopping_shorts import media_download as md
    monkeypatch.setattr(md.config, "INSTAGRAM_SESSION_PATH", "")
    assert md._cookies_arg("https://www.instagram.com/reel/XYZ/") == []


# ── ★1·★2 최종리뷰 수정: 쓰레드 다운로드 경로 + 인스타 오분류 방지 (2026-08-17) ──

def test_route_threads_calls_download_threads(monkeypatch, tmp_path):
    """download_any가 쓰레드 URL을 _download_threads로 보낸다(그동안 '지원하지
    않는 URL' RuntimeError로 100% 실패하던 구멍)."""
    called = {}

    def fake_threads(url, d):
        called["threads"] = url
        return str(tmp_path / "threads.mp4"), "캡션"
    monkeypatch.setattr(md, "_download_threads", fake_threads)
    monkeypatch.setattr(md, "_download_ytdlp",
                        lambda url, d: (_ for _ in ()).throw(AssertionError("ytdlp 호출됨")))
    path, caption = md.download_any(
        "https://www.threads.com/@jiniggultem/post/DcIknZjEQVW", str(tmp_path))
    assert called["threads"].endswith("/post/DcIknZjEQVW")
    assert path.endswith("threads.mp4")
    assert caption == "캡션"


def test_route_threads_net_host_also_matches(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(md, "_download_threads",
                        lambda url, d: called.setdefault("hit", True) or (str(tmp_path / "t.mp4"), ""))
    md.download_any("https://threads.net/@u/post/Abc123", str(tmp_path))
    assert called.get("hit")


def test_threads_cdn_mp4_does_not_route_to_instagram(monkeypatch, tmp_path):
    """★2 회귀 재현: 쓰레드 mp4 주소(cdninstagram.com)가 'instagram.com' 부분문자열
    검사에 걸려 인스타 세션/쿠키 경로로 새어 들어가면 안 된다. 호스트 기반 판정이라면
    이 CDN 주소는 instagram 분기가 아니라 직접 mp4 다운로드로 가야 한다."""
    import shopping_shorts.frame_extract as frame_extract

    def boom_ig(url, d):
        raise AssertionError("쓰레드 CDN mp4가 인스타 분기로 샜다(★2 회귀)")
    monkeypatch.setattr(md, "_download_instagram", boom_ig)
    monkeypatch.setattr(frame_extract, "download_video",
                        lambda video_url, dest: tmp_path / "cdn.mp4")

    url = "https://scontent-ssn1-1.cdninstagram.com/o1/v/t16/f2/m84/AQOp9.mp4?_nc_cat=1"
    path, caption = md.download_any(url, str(tmp_path))
    assert path.endswith("cdn.mp4")
    assert caption == ""


def test_instagram_page_url_still_routes_to_instagram(monkeypatch, tmp_path):
    """인스타 회귀 무결성: 실제 인스타 페이지 URL(www.instagram.com/reel/...)은
    호스트 기반 판정으로 바꾼 뒤에도 여전히 _download_instagram으로 가야 한다."""
    called = {}

    def fake_ig(url, d):
        called["ig"] = url
        return str(tmp_path / "ig.mp4"), "캡션"
    monkeypatch.setattr(md, "_download_instagram", fake_ig)
    path, caption = md.download_any("https://www.instagram.com/reel/ABC/", str(tmp_path))
    assert called["ig"].endswith("/reel/ABC/")
    assert path.endswith("ig.mp4")


def test_download_threads_no_video_raises_clear_error(monkeypatch, tmp_path):
    """영상이 없는 글(이미지·텍스트만)은 무엇이 문제인지 알 수 있는 에러를 낸다."""
    monkeypatch.setattr(md, "_fetch_threads_post",
                        lambda url, timeout=30: {"code": "Abc", "caption": "글만 있음",
                                                  "video_url": ""})
    try:
        md._download_threads("https://www.threads.com/@u/post/Abc", str(tmp_path))
        assert False, "에러가 나야 한다"
    except RuntimeError as e:
        assert "영상이 없는 글" in str(e)


def test_download_threads_post_not_found_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(md, "_fetch_threads_post", lambda url, timeout=30: None)
    try:
        md._download_threads("https://www.threads.com/@u/post/Abc", str(tmp_path))
        assert False, "에러가 나야 한다"
    except RuntimeError as e:
        assert "찾지 못했습니다" in str(e)


def test_download_threads_downloads_video_url(monkeypatch, tmp_path):
    """게시물에 video_url이 있으면 직접 mp4 다운로드 경로(frame_extract.download_video)로
    받는다 — yt-dlp는 쓰레드를 지원하지 않으므로 절대 타면 안 된다."""
    import shopping_shorts.frame_extract as frame_extract
    monkeypatch.setattr(md, "_fetch_threads_post",
                        lambda url, timeout=30: {"code": "Abc", "caption": "캡션임",
                                                  "video_url": "https://scontent.cdninstagram.com/x.mp4"})
    calls = {}

    def fake_download_video(video_url, dest):
        calls["video_url"] = video_url
        return tmp_path / "threads.mp4"
    monkeypatch.setattr(frame_extract, "download_video", fake_download_video)

    path, caption = md._download_threads("https://www.threads.com/@u/post/Abc", str(tmp_path))
    assert calls["video_url"] == "https://scontent.cdninstagram.com/x.mp4"
    assert path.endswith("threads.mp4")
    assert caption == "캡션임"


def test_probe_grab_meta_threads_forwards_timeout(monkeypatch):
    """probe_grab_meta(url, timeout=40) 호출 시 쓰레드 분기가 그 timeout을
    _probe_threads_meta에 실제로 넘겨야 한다(넘기지 않으면 기본 30초로 새 나감)."""
    captured = {}

    def fake_probe(url, timeout=30):
        captured["timeout"] = timeout
        return {}
    monkeypatch.setattr(md, "_probe_threads_meta", fake_probe)
    md.probe_grab_meta("https://www.threads.com/@u/post/Abc", timeout=40)
    assert captured["timeout"] == 40
