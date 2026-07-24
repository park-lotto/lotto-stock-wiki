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


from shopping_shorts.reddit_source import normalize_children


def test_normalize_keeps_only_videos_and_maps_fields():
    children = [
        {"data": {"id": "aaa", "title": "wow clip", "ups": 1200, "num_comments": 45,
                  "created_utc": 1785000000, "permalink": "/r/x/comments/aaa/",
                  "subreddit": "nextfuckinglevel", "url": "https://www.tiktok.com/@z/video/9",
                  "is_video": False, "media": None, "thumbnail": "https://thumb/aaa.jpg"}},
        {"data": {"id": "bbb", "title": "just a photo", "ups": 5, "num_comments": 0,
                  "created_utc": 1785000000, "permalink": "/r/x/comments/bbb/",
                  "subreddit": "nextfuckinglevel", "url": "https://i.redd.it/p.jpg",
                  "domain": "i.redd.it"}},
    ]
    items = normalize_children(children, category="테스트")
    assert len(items) == 1
    it = items[0]
    assert it["post_id"] == "aaa"
    assert it["shortcode"] == "aaa"          # ranking._normalize가 쓰는 키
    assert it["source"] == "reddit"
    assert it["media_platform"] == "tiktok"
    assert it["media_url"] == "https://www.tiktok.com/@z/video/9"
    assert it["ups"] == 1200
    assert it["category"] == "테스트"
    assert it["published_at"].endswith("Z")
    assert it["permalink"] == "https://www.reddit.com/r/x/comments/aaa/"


import shopping_shorts.reddit_source as rs


def test_fetch_subreddit_parses_listing(monkeypatch):
    fake = ('{"data":{"children":[{"data":{"id":"aaa","title":"t","ups":10,'
            '"num_comments":1,"created_utc":1785000000,"permalink":"/r/x/comments/aaa/",'
            '"subreddit":"x","url":"https://youtu.be/z","is_video":false,"media":null,'
            '"thumbnail":"https://th/aaa.jpg"}}]}}')
    monkeypatch.setattr(rs, "_http_get", lambda url, timeout=15: fake)
    items = rs.fetch_subreddit("x", category="테스트", sort="rising", limit=50)
    assert len(items) == 1 and items[0]["media_platform"] == "youtube"


def test_fetch_subreddit_swallows_errors(monkeypatch):
    def boom(url, timeout=15):
        raise RuntimeError("429")
    monkeypatch.setattr(rs, "_http_get", boom)
    monkeypatch.setattr(rs.time, "sleep", lambda *_: None)
    assert rs.fetch_subreddit("x", category="테스트") == []   # 부분실패 허용
