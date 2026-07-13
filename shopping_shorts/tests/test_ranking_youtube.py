from datetime import datetime, timezone
from shopping_shorts import ranking


def test_build_youtube_items_views_based():
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    raw = [{
        "video_id": "vid1", "channel_id": "ch1", "channel_title": "살림TV",
        "title": "오이 보관법", "description": "d", "thumbnail": "http://t.jpg",
        "published_at": "2026-07-12T00:00:00Z",  # 24h 전
        "views": 24000, "likes": 1200, "comments": 24,
    }]
    items = ranking.build_youtube_items(raw, prev_base=lambda sc: None,
                                        prev_delta=lambda sc: None, now=now)
    it = items[0]
    assert it["platform"] == "youtube"
    assert it["shortcode"] == "vid1"
    assert it["base_count"] == 24000 and it["views"] == 24000
    assert it["speed"] == 1000.0                       # 24000 / 24h
    assert round(it["density"], 4) == round(1224 / 24000, 4)   # (likes+comments)/views
    assert it["is_new"] is True and it["url"].endswith("vid1")
