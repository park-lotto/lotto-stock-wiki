import pytest
from shopping_shorts import xiaohongshu_search
from shopping_shorts import xiaohongshu_search as xhs


def test_search_returns_normalized_candidates(monkeypatch):
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", ["fake-key"])
    captured = {}

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        captured["payload"] = payload
        captured["actor"] = actor
        return [{
            "url": "https://www.xiaohongshu.com/discovery/item/abc123",
            "type": "video",
            "title": "실링팬 개봉기",
            "video": {"url_720p": "https://sns-video.xhscdn.com/v.mp4", "thumbnail": "https://sns.xhscdn.com/t.jpg"},
        }]

    monkeypatch.setattr(xiaohongshu_search, "_run_with_rotation", fake_run_with_rotation)

    results = xiaohongshu_search.search("실링팬", max_results=10)

    assert results == [{
        "url": "https://www.xiaohongshu.com/discovery/item/abc123",
        "title": "실링팬 개봉기",
        "thumbnail": "https://sns.xhscdn.com/t.jpg",
        "play_url": "https://sns-video.xhscdn.com/v.mp4",
        "channel": "",
        "likes": None,
        "views": None,
        "duration": None,
        "is_short": True,
    }]
    assert captured["payload"]["keywords"] == ["실링팬"]
    assert captured["payload"]["maxResults"] == 10
    assert captured["payload"]["noteType"] == "video"
    assert captured["actor"] == "zen-studio~rednote-search-scraper"


def test_search_falls_back_to_desc_when_title_empty(monkeypatch):
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [{
            "url": "https://www.xiaohongshu.com/discovery/item/x",
            "type": "video", "title": "", "desc": "설명만 있음",
            "video": {"url_720p": "v.mp4", "thumbnail": "t.jpg"},
        }]
    monkeypatch.setattr(xiaohongshu_search, "_run_with_rotation", fake_run_with_rotation)

    results = xiaohongshu_search.search("x")
    assert results[0]["title"] == "설명만 있음"


def test_search_skips_image_notes_without_video(monkeypatch):
    """noteType=video로 요청해도 사진 노트가 섞여 나올 가능성 대비 이중 확인."""
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [
            {"url": "https://www.xiaohongshu.com/discovery/item/photo", "type": "image", "title": "사진", "video": {}},
            {"url": "https://www.xiaohongshu.com/discovery/item/vid", "type": "video", "title": "영상",
             "video": {"url_720p": "v.mp4", "thumbnail": "t.jpg"}},
        ]
    monkeypatch.setattr(xiaohongshu_search, "_run_with_rotation", fake_run_with_rotation)

    results = xiaohongshu_search.search("x")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.xiaohongshu.com/discovery/item/vid"


def test_search_extracts_channel_likes_and_duration(monkeypatch):
    """메타 추출 계약 — 2026-07-18 서버 실측 스키마(author.nickname·engagement.liked_count·
    video.duration_seconds·images 커버)를 고정한다. ★video.thumbnail은 스프라이트라 안 쓴다."""
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [{
            "url": "https://www.xiaohongshu.com/discovery/item/meta",
            "type": "video", "title": "청소기 리뷰",
            "cover_image_index": 0,
            "images": [{"url": "https://sns.xhscdn.com/cover0.jpg"}, {"url": "c1.jpg"}],
            "author": {"userid": "u1", "nickname": "살림요정"},
            "engagement": {"liked_count": 1200, "comments_count": 30, "collected_count": 90},
            "video": {"url_720p": "v.mp4", "thumbnail": "SPRITE_GRID.jpg",
                      "duration_seconds": 240},
        }]
    monkeypatch.setattr(xiaohongshu_search, "_run_with_rotation", fake_run_with_rotation)

    r = xiaohongshu_search.search("청소기")[0]
    assert r["channel"] == "살림요정"
    assert r["likes"] == 1200
    assert r["duration"] == 240
    assert r["is_short"] is False   # 240초 > 90초
    assert r["thumbnail"] == "https://sns.xhscdn.com/cover0.jpg"   # ★images 커버
    assert "SPRITE" not in r["thumbnail"]                          # 스프라이트 금지


def test_cover_falls_back_to_video_thumbnail_when_no_images(monkeypatch):
    """images가 없으면 first_frame → video.thumbnail 순으로 폴백."""
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", ["fake-key"])

    def fake_run_with_rotation(payload, tokens, timeout, poll_interval, actor=None):
        return [{
            "url": "https://www.xiaohongshu.com/discovery/item/nf",
            "type": "video", "title": "짧은거",
            "video": {"url_720p": "v.mp4", "thumbnail": "t.jpg", "duration_seconds": 45},
        }]
    monkeypatch.setattr(xiaohongshu_search, "_run_with_rotation", fake_run_with_rotation)

    r = xiaohongshu_search.search("x")[0]
    assert r["duration"] == 45
    assert r["is_short"] is True
    assert r["thumbnail"] == "t.jpg"


def test_search_no_tokens_raises(monkeypatch):
    monkeypatch.setattr(xiaohongshu_search, "APIFY_TOKENS", [])
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        xiaohongshu_search.search("x")


def test_search_full_maps_engagement_schema(monkeypatch):
    monkeypatch.setattr(xhs, "APIFY_TOKENS", ["fake-key"])

    def fake_run(payload, tokens, timeout, poll_interval, actor=None):
        return [{
            "url": "https://www.xiaohongshu.com/explore/abc", "type": "video", "id": "abc",
            "title": "厨房好物", "timestamp": 1779088572,
            "video": {"url_720p": "https://v.mp4", "duration_seconds": 25},
            "images": [{"url": "https://cover.jpg"}], "cover_image_index": 0,
            "author": {"userid": "u_kim", "nickname": "김철수"},
            "engagement": {"liked_count": 300, "comments_count": 12,
                           "collected_count": 90, "shared_count": 7},
        }]
    monkeypatch.setattr(xhs, "_run_with_rotation", fake_run)

    out = xhs.search_full("厨房好物", max_results=40)
    assert len(out) == 1
    r = out[0]
    assert r["video_id"] == "abc" and r["media_platform"] == "xiaohongshu"
    assert r["published_at"] == "2026-05-18T07:16:12Z"   # 1779088572 → ISO(UTC)
    assert r["likes"] == 300 and r["comments"] == 12 and r["collects"] == 90 and r["shares"] == 7
    assert r["views"] == 0 and r["channel_title"] == "김철수" and r["thumbnail"] == "https://cover.jpg"
    assert r["channel_id"] == "u_kim"   # 계정 발굴 집계·프로필URL 조립용(author.userid)


def test_search_full_skips_non_video(monkeypatch):
    monkeypatch.setattr(xhs, "APIFY_TOKENS", ["fake-key"])
    monkeypatch.setattr(xhs, "_run_with_rotation",
                        lambda *a, **k: [{"url": "u", "type": "normal", "id": "x"}])
    assert xhs.search_full("x") == []
