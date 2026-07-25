from shopping_shorts.ranking import aggregate_channels


ITEMS = [
    {"username": "UCa", "name": "채널A", "views": 1000, "speed": 50.0, "density": 0.10,
     "accel": 5, "score": 0.9, "grade": "🔥", "thumbnail": "ta1"},
    {"username": "UCa", "name": "채널A", "views": 500, "speed": 80.0, "density": 0.20,
     "accel": -2, "score": 0.4, "grade": "—", "thumbnail": "ta2"},
    {"username": "UCb", "name": "채널B", "views": 3000, "speed": 30.0, "density": 0.05,
     "accel": 1, "score": 0.7, "grade": "⚡", "thumbnail": "tb1"},
    {"username": None, "name": "무채널", "views": 999},   # username 없으면 제외
]


def test_aggregate_groups_and_metrics():
    rows = aggregate_channels(ITEMS, sort="views")
    assert [r["channel_id"] for r in rows] == ["UCb", "UCa"]   # views 합 내림차순(3000 vs 1500)
    a = next(r for r in rows if r["channel_id"] == "UCa")
    assert a["video_count"] == 2
    assert a["views"] == 1500                # 1000+500
    assert a["speed"] == 80.0                # 최고 속도
    assert a["density"] == 0.15              # (0.10+0.20)/2
    assert a["accel"] == 3                   # 5+(-2)
    assert a["grade"] == "🔥"                # 최고점(0.9) 영상 등급
    assert a["thumbnail"] == "ta1"
    assert a["channel_url"] == "https://www.youtube.com/channel/UCa"


def test_sort_by_speed_and_accel():
    assert aggregate_channels(ITEMS, sort="speed")[0]["channel_id"] == "UCa"   # 80 > 30
    assert aggregate_channels(ITEMS, sort="accel")[0]["channel_id"] == "UCa"   # 3 > 1


def test_excludes_null_channel():
    rows = aggregate_channels(ITEMS)
    assert all(r["channel_id"] for r in rows)
    assert len(rows) == 2
