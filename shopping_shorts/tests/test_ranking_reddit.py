from datetime import datetime, timezone
from shopping_shorts.ranking import build_reddit_items, apply_grades

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def _reddit_item(pid, ups, comments, hours_ago):
    ts = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc).timestamp() - hours_ago * 3600
    return {"source": "reddit", "post_id": pid, "shortcode": pid, "title": "t",
            "media_url": "https://x", "media_platform": "tiktok", "thumbnail": "",
            "ups": ups, "num_comments": comments,
            "published_at": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "category": "테스트"}


def test_build_reddit_items_speed_and_newness():
    raw = [_reddit_item("aaa", 1200, 60, hours_ago=4)]
    items = build_reddit_items(raw, prev_base=lambda sc: None, prev_delta=lambda sc: None, now=NOW)
    assert len(items) == 1
    it = items[0]
    assert it["base_count"] == 1200
    assert it["is_new"] is True
    assert it["speed"] == 300.0                 # 1200 / 4h
    assert round(it["density"], 3) == 0.05       # 60 / 1200
    assert it["accel"] is None                    # 첫 스냅샷


def test_build_reddit_items_filters_old():
    raw = [_reddit_item("old", 999, 10, hours_ago=100)]   # window 48h 밖
    assert build_reddit_items(raw, lambda sc: None, lambda sc: None, now=NOW) == []


def test_apply_grades_runs_on_reddit_items():
    raw = [_reddit_item("aaa", 1200, 60, 4), _reddit_item("bbb", 100, 2, 4)]
    items = apply_grades(build_reddit_items(raw, lambda sc: None, lambda sc: None, now=NOW))
    assert items[0]["score"] >= items[1]["score"] or "grade" in items[0]
