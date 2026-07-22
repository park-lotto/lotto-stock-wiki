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


class _Resp403:
    status_code = 403
    def json(self): return {}
    def raise_for_status(self): pass


def test_enrich_youtube_partial_failure_degrades(monkeypatch):
    """videos는 성공, channels·commentThreads는 실패 → 비디오 필드는 채우고
    channel_name/top_comments 등은 빈값으로 degrade(best-effort, 크래시 없음)."""
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["k1"])
    def fake_get(url, params=None, timeout=None):
        if "videos" in url:
            return _Resp({"items": [{"snippet": {"title": "T", "description": "설명",
                "channelId": "CID", "publishedAt": "2026-07-01T00:00:00Z"},
                "statistics": {"viewCount": "1000", "likeCount": "50", "commentCount": "7"}}]})
        if "channels" in url:
            raise RuntimeError("boom")
        if "commentThreads" in url:
            raise RuntimeError("boom")
        raise AssertionError(url)
    monkeypatch.setattr(yc.requests, "get", fake_get)
    r = yc.enrich_youtube("https://youtu.be/abc123DEF45")
    assert r is not None
    assert r["views"] == 1000 and r["likes"] == 50 and r["comment_count"] == 7
    assert r["channel_name"] == ""
    assert r["subscribers"] == 0
    assert r["top_comments"] == []


def test_enrich_youtube_all_keys_quota(monkeypatch):
    """videos 조회에서 모든 키가 403(쿼터/권한)이면 {"status": "quota"}."""
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["k1", "k2"])
    def fake_get(url, params=None, timeout=None):
        return _Resp403()
    monkeypatch.setattr(yc.requests, "get", fake_get)
    r = yc.enrich_youtube("https://youtu.be/abc123DEF45")
    assert r == {"status": "quota"}


def test_enrich_youtube_video_not_found(monkeypatch):
    """videos 조회는 성공했지만 items가 비어있으면(영상 없음) None — quota 아님."""
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["k1"])
    def fake_get(url, params=None, timeout=None):
        if "videos" in url:
            return _Resp({"items": []})
        raise AssertionError(url)
    monkeypatch.setattr(yc.requests, "get", fake_get)
    r = yc.enrich_youtube("https://youtu.be/abc123DEF45")
    assert r is None


def test_enrich_youtube_network_failure_not_quota(monkeypatch):
    """videos 조회가 전부 실패해도 403(쿼터)이 아니라 네트워크/기타 예외면 None — quota 오표기 금지."""
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["k1", "k2"])
    def fake_get(url, params=None, timeout=None):
        if "videos" in url:
            raise ConnectionError("network down")
        raise AssertionError(url)
    monkeypatch.setattr(yc.requests, "get", fake_get)
    r = yc.enrich_youtube("https://youtu.be/abc123DEF45")
    assert r is None


def test_enrich_youtube_skips_malformed_comment(monkeypatch):
    """삭제/모더레이션된 댓글(topLevelComment 없음)은 KeyError로 크래시하지 않고 스킵."""
    monkeypatch.setattr(yc, "YOUTUBE_API_KEYS", ["k1"])
    def fake_get(url, params=None, timeout=None):
        if "videos" in url:
            return _Resp({"items": [{"snippet": {"title": "T", "description": "d",
                "channelId": "CID", "publishedAt": "2026-07-01T00:00:00Z"},
                "statistics": {"viewCount": "1", "likeCount": "1", "commentCount": "1"}}]})
        if "channels" in url:
            return _Resp({"items": [{"snippet": {"title": "채널", "customUrl": "@c"},
                "statistics": {"subscriberCount": "1"}}]})
        if "commentThreads" in url:
            return _Resp({"items": [
                {"snippet": {}},  # 삭제/모더레이션된 댓글 — topLevelComment 없음
                {"snippet": {"topLevelComment": {"snippet":
                    {"authorDisplayName": "B", "textDisplay": "정상댓글", "likeCount": 2}}}},
            ]})
        raise AssertionError(url)
    monkeypatch.setattr(yc.requests, "get", fake_get)
    r = yc.enrich_youtube("https://youtu.be/abc123DEF45")
    assert len(r["top_comments"]) == 1
    assert r["top_comments"][0] == {"author": "B", "text": "정상댓글", "likes": 2}
