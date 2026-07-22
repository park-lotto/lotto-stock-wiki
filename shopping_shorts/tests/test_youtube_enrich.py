from shopping_shorts.youtube_client import video_id_from_url
import shopping_shorts.youtube_client as yc

def test_video_id_from_url_forms():
    assert video_id_from_url("https://www.youtube.com/watch?v=abc123DEF45") == "abc123DEF45"
    assert video_id_from_url("https://youtu.be/abc123DEF45") == "abc123DEF45"
    assert video_id_from_url("https://www.youtube.com/shorts/abc123DEF45") == "abc123DEF45"
    assert video_id_from_url("https://www.youtube.com/watch?v=abc123DEF45&t=10s") == "abc123DEF45"
    assert video_id_from_url("https://www.tiktok.com/@x/video/123") is None
    assert video_id_from_url("") is None


class _Resp:
    def __init__(self, data): self._d = data; self.status_code = 200
    def json(self): return self._d
    def raise_for_status(self): pass

def test_enrich_youtube_combines(monkeypatch):
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["k1"])
    def fake_get(url, params=None, timeout=None):
        if "videos" in url:
            return _Resp({"items": [{"snippet": {"title": "T", "description": "설명전문 #해시",
                "channelId": "CID", "publishedAt": "2026-07-01T00:00:00Z"},
                "statistics": {"viewCount": "1000", "likeCount": "50", "commentCount": "7"}}]})
        if "channels" in url:
            return _Resp({"items": [{"snippet": {"title": "채널명", "customUrl": "@chan"},
                "statistics": {"subscriberCount": "12345"}}]})
        if "commentThreads" in url:
            return _Resp({"items": [{"snippet": {"topLevelComment": {"snippet":
                {"authorDisplayName": "A", "textDisplay": "댓글1", "likeCount": 3}}}}]})
        raise AssertionError(url)
    monkeypatch.setattr(yc.requests, "get", fake_get)
    r = yc.enrich_youtube("https://youtu.be/abc123DEF45")
    assert r["channel_name"] == "채널명"
    assert r["subscribers"] == 12345
    assert r["channel_url"] == "https://www.youtube.com/@chan"
    assert r["views"] == 1000 and r["likes"] == 50 and r["comment_count"] == 7
    assert r["caption"] == "설명전문 #해시"
    assert r["upload_date"].startswith("2026-07-01")
    assert r["top_comments"][0] == {"author": "A", "text": "댓글1", "likes": 3}

def test_enrich_youtube_non_youtube_url():
    assert yc.enrich_youtube("https://www.tiktok.com/@x/video/1") is None
