from datetime import datetime, timezone
from shopping_shorts.ranking import build_overseas_items


def _raw(**kw):
    base = {"video_id": "v1", "title": "kitchen gadget", "published_at": "2026-07-25T12:00:00Z",
            "views": 0, "likes": 100, "comments": 10, "collects": 40, "shares": 5,
            "channel_title": "a", "thumbnail": "t", "url": "u", "media_platform": "douyin"}
    base.update(kw); return base


def test_speed_uses_engagement_not_views():
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)  # 24h 후
    items = build_overseas_items([_raw()], lambda sc: None, lambda sc: None, now=now)
    it = items[0]
    assert it["base_count"] == 155          # 100+10+40+5
    assert round(it["speed"], 1) == round(155 / 24, 1)
    assert it["platform"] == "douyin"       # media_platform 보존
    assert it["views"] == 0                  # 표시용, CN은 0


def test_out_of_window_excluded():
    now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)  # >336h
    assert build_overseas_items([_raw()], lambda sc: None, lambda sc: None, now=now) == []


def test_accel_from_prev_delta():
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    items = build_overseas_items([_raw()], lambda sc: 55, lambda sc: 50, now=now)
    assert items[0]["delta"] == 100          # 155 - prev_base 55
    assert items[0]["accel"] == 50           # delta 100 - prev_delta 50
