from shopping_shorts.reddit_source import extract_media_url


def _post(**kw):
    base = {"is_video": False, "media": None, "url": "", "domain": "", "post_hint": ""}
    base.update(kw)
    return base


def test_reddit_hosted_video():
    p = _post(is_video=True,
              media={"reddit_video": {"fallback_url": "https://v.redd.it/abc/DASH_720.mp4"}})
    url, platform = extract_media_url(p)
    assert url == "https://v.redd.it/abc/DASH_720.mp4"
    assert platform == "reddit"


def test_external_tiktok():
    url, platform = extract_media_url(_post(url="https://www.tiktok.com/@x/video/123"))
    assert platform == "tiktok"
    assert url == "https://www.tiktok.com/@x/video/123"


def test_external_youtube_short():
    url, platform = extract_media_url(_post(url="https://youtu.be/abc123"))
    assert platform == "youtube"


def test_image_post_returns_none():
    url, platform = extract_media_url(_post(url="https://i.redd.it/pic.jpg", domain="i.redd.it"))
    assert url is None and platform is None


def test_selfpost_returns_none():
    url, platform = extract_media_url(_post(url="https://www.reddit.com/r/x/comments/..", domain="self.x"))
    assert url is None and platform is None
