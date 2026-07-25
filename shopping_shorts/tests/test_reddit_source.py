import urllib.error

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
    monkeypatch.setattr(rs, "_has_oauth", lambda: False)   # RSS 폴백 강제
    monkeypatch.setattr(rs, "_http_get", lambda url, timeout=15: _ATOM_XML)
    items = rs.fetch_subreddit("x", category="테스트", sort="rising", limit=50)
    assert len(items) == 1 and items[0]["media_platform"] == "tiktok"


def test_fetch_subreddit_swallows_errors(monkeypatch):
    monkeypatch.setattr(rs, "_has_oauth", lambda: False)
    def boom(url, timeout=15):
        raise RuntimeError("403")
    monkeypatch.setattr(rs, "_http_get", boom)
    monkeypatch.setattr(rs.time, "sleep", lambda *_: None)
    assert rs.fetch_subreddit("x", category="테스트") == []   # 부분실패 허용


# ── 429 백오프(익명 RSS·데이터센터 IP) ──
class _FakeOpener:
    def __init__(self, exc):
        self._exc = exc
    def open(self, req, timeout=15):
        raise self._exc


def test_http_get_maps_429_to_ratelimited(monkeypatch):
    exc = urllib.error.HTTPError(
        "https://www.reddit.com/r/x/rising.rss", 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(rs, "_opener", lambda: _FakeOpener(exc))
    import pytest
    with pytest.raises(rs.RateLimited):
        rs._http_get("https://www.reddit.com/r/x/rising.rss")


def test_http_get_non_429_propagates(monkeypatch):
    exc = urllib.error.HTTPError(
        "https://www.reddit.com/r/x/rising.rss", 403, "Forbidden", {}, None)
    monkeypatch.setattr(rs, "_opener", lambda: _FakeOpener(exc))
    import pytest
    with pytest.raises(urllib.error.HTTPError):
        rs._http_get("https://www.reddit.com/r/x/rising.rss")


def test_fetch_subreddit_retries_on_429_then_succeeds(monkeypatch):
    # 429 두 번 → 세 번째 성공. 백오프 재시도가 실제로 통과시킨다.
    monkeypatch.setattr(rs, "_has_oauth", lambda: False)
    monkeypatch.setattr(rs.time, "sleep", lambda *_: None)
    calls = {"n": 0}
    def flaky(url, timeout=15):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise rs.RateLimited(url)
        return _ATOM_XML
    monkeypatch.setattr(rs, "_http_get", flaky)
    monkeypatch.setattr(rs, "_RL_RETRIES", 3)
    monkeypatch.setattr(rs, "_RL_BACKOFF", [0.0, 0.0, 0.0])
    items = rs.fetch_subreddit("x", category="테스트")
    assert len(items) == 1 and calls["n"] == 3


def test_fetch_subreddit_429_gives_up_after_retries(monkeypatch):
    # 계속 429면 _RL_RETRIES 소진 후 빈손(무한루프 아님).
    monkeypatch.setattr(rs, "_has_oauth", lambda: False)
    monkeypatch.setattr(rs.time, "sleep", lambda *_: None)
    calls = {"n": 0}
    def always_429(url, timeout=15):
        calls["n"] += 1
        raise rs.RateLimited(url)
    monkeypatch.setattr(rs, "_http_get", always_429)
    monkeypatch.setattr(rs, "_RL_RETRIES", 3)
    monkeypatch.setattr(rs, "_RL_BACKOFF", [0.0, 0.0, 0.0])
    assert rs.fetch_subreddit("x") == []
    assert calls["n"] == 4          # 최초 1 + 재시도 3


# ── 프록시(주거용 IP) ──
def test_proxies_none_when_unset(monkeypatch):
    monkeypatch.setattr(rs, "REDDIT_PROXY", "")
    assert rs._proxies() is None


def test_proxies_dict_when_set(monkeypatch):
    monkeypatch.setattr(rs, "REDDIT_PROXY", "http://u:p@host:80")
    assert rs._proxies() == {"http": "http://u:p@host:80", "https": "http://u:p@host:80"}


def test_opener_uses_proxy_handler_when_set(monkeypatch):
    monkeypatch.setattr(rs, "REDDIT_PROXY", "http://u:p@host:80")
    op = rs._opener()
    assert any(isinstance(h, rs.urllib.request.ProxyHandler) for h in op.handlers)


# ── OAuth(권장 경로) ──
def test_normalize_children_json_real_upvotes():
    children = [
        {"data": {"id": "aaa", "title": "wow", "ups": 5200, "num_comments": 88,
                  "created_utc": 1785000000, "permalink": "/r/x/comments/aaa/wow/",
                  "subreddit": "x", "is_video": True,
                  "media": {"reddit_video": {"fallback_url": "https://v.redd.it/aaa/DASH.mp4"}},
                  "thumbnail": "https://th/a.jpg"}},
        {"data": {"id": "bbb", "title": "photo", "ups": 3, "url": "https://i.redd.it/p.jpg"}},
    ]
    items = rs.normalize_children(children, category="테스트")
    assert len(items) == 1                       # 이미지 제외
    it = items[0]
    assert it["ups"] == 5200 and it["num_comments"] == 88   # 실업보트
    assert it["media_platform"] == "reddit"
    assert it["media_url"] == "https://v.redd.it/aaa/DASH.mp4"
    assert it["permalink"] == "https://www.reddit.com/r/x/comments/aaa/wow/"
    assert it["shortcode"] == "aaa" and it["category"] == "테스트"


def test_oauth_token_cached(monkeypatch):
    calls = {"n": 0}

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"access_token": "TOK", "expires_in": 3600}

    def fake_post(url, **kw):
        calls["n"] += 1
        return _Resp()

    monkeypatch.setattr(rs.requests, "post", fake_post)
    rs._TOKEN.update(token=None, exp=0.0)
    assert rs._oauth_token() == "TOK"
    assert rs._oauth_token() == "TOK"      # 캐시 재사용
    assert calls["n"] == 1                  # POST 1번만


def test_fetch_oauth_parses_json(monkeypatch):
    monkeypatch.setattr(rs, "_oauth_token", lambda: "TOK")

    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"data": {"children": [
                {"data": {"id": "zz", "title": "t", "ups": 999, "num_comments": 4,
                          "created_utc": 1785000000, "permalink": "/r/x/comments/zz/t/",
                          "subreddit": "x", "url": "https://www.tiktok.com/@z/video/1"}}]}}

    captured = {}

    def fake_get(url, **kw):
        captured["url"] = url
        return _Resp()

    monkeypatch.setattr(rs.requests, "get", fake_get)
    items = rs._fetch_oauth("x", "테스트", "top", 50)
    assert "oauth.reddit.com/r/x/top" in captured["url"]
    assert len(items) == 1 and items[0]["ups"] == 999 and items[0]["media_platform"] == "tiktok"


def test_fetch_subreddit_uses_oauth_when_creds(monkeypatch):
    monkeypatch.setattr(rs, "_has_oauth", lambda: True)
    monkeypatch.setattr(rs, "_fetch_oauth",
                        lambda sub, cat, sort, limit: [{"shortcode": "oauth"}])
    monkeypatch.setattr(rs, "_fetch_rss",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("RSS 타면 안됨")))
    assert rs.fetch_subreddit("x", sort="top")[0]["shortcode"] == "oauth"


def test_normalize_entries_html_entity_decoded():
    # 실제 RSS는 XML+HTML 이중 이스케이프 → 와이어상 &amp;는 XML소스에 &amp;amp;로 온다.
    # ET가 한 겹, html.unescape가 나머지 겹을 풀어 URL의 &가 온전해야 한다(서명 썸네일).
    xml = ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>'
           '<title>t</title><id>t3_zz</id>'
           '<link href="https://www.reddit.com/r/x/comments/zz/t/"/>'
           '<published>2026-07-25T10:00:00+00:00</published>'
           '<content type="html">&lt;a href="https://youtu.be/zz?a=1&amp;amp;b=2"&gt;x&lt;/a&gt; '
           '&lt;img src="https://preview.redd.it/z.jpg?w=108&amp;amp;s=sig"&gt;</content>'
           '</entry></feed>')
    it = normalize_entries(xml, subreddit="x")[0]
    assert it["media_url"] == "https://youtu.be/zz?a=1&b=2"
    assert it["thumbnail"] == "https://preview.redd.it/z.jpg?w=108&s=sig"
    assert "&amp;" not in it["thumbnail"] and "&amp;" not in it["media_url"]
