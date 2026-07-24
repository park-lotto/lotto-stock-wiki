from shopping_shorts.reddit_source import extract_media_url, normalize_entries
import shopping_shorts.reddit_source as rs


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


# ── RSS(Atom) 정규화 ──
_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>wow clip</title>
    <id>t3_aaa</id>
    <link href="https://www.reddit.com/r/x/comments/aaa/wow_clip/"/>
    <published>2026-07-25T10:00:00+00:00</published>
    <content type="html">&lt;a href="https://www.tiktok.com/@z/video/9"&gt;[link]&lt;/a&gt; &lt;img src="https://th/aaa.jpg"&gt;</content>
  </entry>
  <entry>
    <title>just a photo</title>
    <id>t3_bbb</id>
    <link href="https://www.reddit.com/r/x/comments/bbb/just_a_photo/"/>
    <published>2026-07-25T10:00:00+00:00</published>
    <content type="html">&lt;a href="https://i.redd.it/p.jpg"&gt;[link]&lt;/a&gt;</content>
  </entry>
</feed>"""


def test_normalize_entries_keeps_only_videos_and_maps_fields():
    items = normalize_entries(_ATOM_XML, subreddit="x", category="테스트", sort="top")
    assert len(items) == 1          # 이미지 포스트(bbb)는 제외
    it = items[0]
    assert it["post_id"] == "aaa"
    assert it["shortcode"] == "aaa"          # ranking._normalize가 쓰는 키
    assert it["source"] == "reddit"
    assert it["media_platform"] == "tiktok"
    assert it["media_url"] == "https://www.tiktok.com/@z/video/9"
    assert it["thumbnail"] == "https://th/aaa.jpg"
    assert it["subreddit"] == "x"
    assert it["category"] == "테스트"
    assert it["published_at"] == "2026-07-25T10:00:00+00:00"
    assert it["permalink"] == "https://www.reddit.com/r/x/comments/aaa/wow_clip/"
    assert it["ups"] == 1000                 # 첫 항목 = 순위점수 최고
    assert it["num_comments"] == 0


def test_normalize_entries_rank_points_descend():
    # 영상 항목 3개면 순위점수(ups)가 상단→하단 내림차순이어야 한다.
    entry = ('<entry><title>t</title><id>t3_{i}</id>'
             '<link href="https://www.reddit.com/r/x/comments/{i}/t/"/>'
             '<published>2026-07-25T10:00:00+00:00</published>'
             '<content type="html">&lt;a href="https://youtu.be/{i}"&gt;x&lt;/a&gt;</content></entry>')
    xml = ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
           + "".join(entry.format(i=n) for n in ("aa", "bb", "cc")) + "</feed>")
    ups = [it["ups"] for it in normalize_entries(xml, subreddit="x")]
    assert ups == [1000, 990, 980]


def test_fetch_subreddit_parses_rss(monkeypatch):
    monkeypatch.setattr(rs, "_http_get", lambda url, timeout=15: _ATOM_XML)
    items = rs.fetch_subreddit("x", category="테스트", sort="rising", limit=50)
    assert len(items) == 1 and items[0]["media_platform"] == "tiktok"


def test_fetch_subreddit_swallows_errors(monkeypatch):
    def boom(url, timeout=15):
        raise RuntimeError("403")
    monkeypatch.setattr(rs, "_http_get", boom)
    monkeypatch.setattr(rs.time, "sleep", lambda *_: None)
    assert rs.fetch_subreddit("x", category="테스트") == []   # 부분실패 허용
