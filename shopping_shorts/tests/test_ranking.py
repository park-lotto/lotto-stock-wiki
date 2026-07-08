from datetime import datetime, timezone, timedelta
from shopping_shorts.ranking import (
    hours_since, build_items, sort_by, grade_from_scores,
)


NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def test_hours_since():
    ts = (NOW - timedelta(hours=10)).isoformat()
    assert round(hours_since(ts, now=NOW)) == 10

def test_build_items_filters_by_window():
    reels = [
        {"shortcode": "new", "timestamp": (NOW - timedelta(hours=5)).isoformat(),
         "commentsCount": 600, "likesCount": 10, "videoViewCount": 100,
         "displayUrl": "t.jpg", "url": "u", "caption": ""},
        {"shortcode": "old", "timestamp": (NOW - timedelta(hours=60)).isoformat(),
         "commentsCount": 900, "likesCount": 10, "videoViewCount": 100,
         "displayUrl": "t.jpg", "url": "u2", "caption": ""},
    ]
    meta = {"name": "테스트", "followers": 1000, "inpock": "i", "username": "u"}
    items = build_items(reels, meta, prev_comments=lambda sc: None,
                        prev_delta=lambda sc: None, now=NOW, window_hours=48)
    # 60시간 지난 'old'는 제외, 'new'만 남음
    assert len(items) == 1
    it = items[0]
    assert it["shortcode"] == "new"
    assert it["comments"] == 600
    assert round(it["age_hours"]) == 5
    assert it["delta"] == 600            # 직전값 없으면 delta = comments (신규)
    assert it["is_new"] is True
    assert round(it["speed"], 1) == 120.0  # 600 / 5h
    assert round(it["density"], 3) == 0.6  # 600 / 1000

def test_build_items_delta_and_accel():
    reels = [{"shortcode": "x", "timestamp": (NOW - timedelta(hours=10)).isoformat(),
              "commentsCount": 1400, "likesCount": 0, "videoViewCount": 0,
              "displayUrl": "", "url": "", "caption": ""}]
    meta = {"name": "n", "followers": 100, "inpock": "", "username": "u"}
    items = build_items(reels, meta,
                        prev_comments=lambda sc: 600,   # 어제 600
                        prev_delta=lambda sc: 200,       # 어제 Δ 200
                        now=NOW, window_hours=48)
    it = items[0]
    assert it["delta"] == 800            # 1400 - 600
    assert it["is_new"] is False
    assert it["accel"] == 600            # 오늘Δ 800 - 어제Δ 200

def test_sort_by_speed_desc():
    items = [{"speed": 10}, {"speed": 99}, {"speed": 50}]
    ranked = sort_by(items, "speed")
    assert [i["speed"] for i in ranked] == [99, 50, 10]

def test_grade_thresholds():
    assert grade_from_scores(0.9) == "🔥🔥🔥"
    assert grade_from_scores(0.6) == "🔥🔥"
    assert grade_from_scores(0.3) == "🔥"
    assert grade_from_scores(0.1) == "—"
