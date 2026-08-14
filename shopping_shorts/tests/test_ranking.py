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
    # 참여밀도 = (좋아요+댓글)/조회수 (2026-08-14 정의 변경, 옛값은 comments/followers=0.6)
    assert round(it["density"], 3) == 6.1  # (10 + 600) / 100


def test_density_uses_views_not_followers():
    """팔로워가 없어도 density가 살아있어야 한다 — 발굴채널이 전부 0으로 죽던 버그(실측 67%)."""
    reels = [{"shortcode": "a", "timestamp": (NOW - timedelta(hours=2)).isoformat(),
              "commentsCount": 40, "likesCount": 60, "videoViewCount": 1000,
              "displayUrl": "", "url": "", "caption": ""}]
    meta = {"name": "발굴채널", "username": "u"}          # followers 키 자체가 없다
    it = build_items(reels, meta, prev_comments=lambda sc: None,
                     prev_delta=lambda sc: None, now=NOW, window_hours=48)[0]
    assert round(it["density"], 3) == 0.1                # (60 + 40) / 1000


def test_density_zero_views_is_safe():
    """조회수 0이어도 ZeroDivisionError 없이 0.0."""
    reels = [{"shortcode": "b", "timestamp": (NOW - timedelta(hours=2)).isoformat(),
              "commentsCount": 5, "likesCount": 5, "videoViewCount": 0,
              "displayUrl": "", "url": "", "caption": ""}]
    it = build_items(reels, {"name": "n", "username": "u"}, prev_comments=lambda sc: None,
                     prev_delta=lambda sc: None, now=NOW, window_hours=48)[0]
    assert it["density"] == 0.0

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

def test_hours_since_naive_timestamp_no_crash():
    # 오프셋 없는(naive) 타임스탬프도 UTC로 간주하고 계산 (크래시 금지)
    naive = "2026-07-08T02:00:00"   # no Z, no offset
    result = hours_since(naive, now=NOW)  # NOW = 2026-07-08 12:00 UTC
    assert round(result) == 10

def test_build_items_survives_naive_timestamp():
    reels = [{"shortcode": "n", "timestamp": "2026-07-08T02:00:00",
              "commentsCount": 100, "likesCount": 0, "videoViewCount": 0,
              "displayUrl": "", "url": "", "caption": ""}]
    meta = {"name": "n", "followers": 100, "inpock": "", "username": "u"}
    items = build_items(reels, meta, prev_comments=lambda sc: None,
                        prev_delta=lambda sc: None, now=NOW, window_hours=48)
    assert len(items) == 1  # 크래시 없이 항목 생성

def test_apply_grades_negative_accel_not_worse_than_none():
    from shopping_shorts.ranking import apply_grades
    # A: 감속중(accel 음수) 강한 영상  B: 이력없음(accel None) 약한 영상
    items = [
        {"shortcode": "A", "speed": 100, "accel": -50, "density": 0.9},
        {"shortcode": "B", "speed": 1,   "accel": None, "density": 0.01},
    ]
    apply_grades(items)
    a = next(i for i in items if i["shortcode"] == "A")
    b = next(i for i in items if i["shortcode"] == "B")
    # 음수 가속이 0(중립)로 처리되어 score가 음수로 안 내려감
    assert a["score"] >= 0
    assert b["score"] >= 0
    # 속도·밀도가 압도적인 A가 B보다 높아야 함
    assert a["score"] > b["score"]

def test_build_items_includes_video_url():
    reels = [{"shortcode": "x", "timestamp": (NOW - timedelta(hours=1)).isoformat(),
              "commentsCount": 10, "likesCount": 0, "videoViewCount": 0,
              "displayUrl": "t.jpg", "url": "u", "caption": "",
              "videoUrl": "https://scontent.cdninstagram.com/video123.mp4"}]
    meta = {"name": "테스트", "followers": 100, "inpock": "", "username": "u"}
    items = build_items(reels, meta, prev_comments=lambda sc: None,
                        prev_delta=lambda sc: None, now=NOW, window_hours=48)
    assert items[0]["video_url"] == "https://scontent.cdninstagram.com/video123.mp4"


def test_new_item_not_penalized_by_missing_accel():
    """처음 잡힌 릴스(accel=None)는 가속 축을 빼고 채점한다 — 신작 자동 감점 방지(2026-08-14)."""
    from shopping_shorts.ranking import apply_grades
    # 속도·밀도는 최고값(=정규화 1.0)인데 accel만 없는 신작
    fresh = {"shortcode": "fresh", "speed": 100.0, "density": 0.5, "accel": None}
    # 같은 속도·밀도인데 가속까지 측정된 기존 항목
    known = {"shortcode": "known", "speed": 100.0, "density": 0.5, "accel": 50}
    apply_grades([fresh, known])
    assert fresh["score"] == 1.0          # 옛 동작이면 2/3 = 0.667로 깎였다
    assert known["score"] == 1.0


def test_accel_zero_is_not_treated_as_missing():
    """가속이 '측정됐는데 0'인 것은 축에 그대로 들어가야 한다(측정불가와 구분)."""
    from shopping_shorts.ranking import apply_grades
    a = {"shortcode": "a", "speed": 10.0, "density": 1.0, "accel": 0}
    b = {"shortcode": "b", "speed": 10.0, "density": 1.0, "accel": 10}
    apply_grades([a, b])
    assert a["score"] < b["score"]        # 0점 가속은 불리한 게 맞다
