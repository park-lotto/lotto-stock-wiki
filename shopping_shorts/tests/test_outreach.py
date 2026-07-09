from shopping_shorts.outreach import goldilocks_score, build_queue


def _item(sc, age, comments, speed):
    return {"shortcode": sc, "age_hours": age, "comments": comments, "speed": speed,
            "name": sc, "url": "u", "thumbnail": "", "category": "기타", "caption": ""}


def test_goldilocks_prefers_recent_low_comments():
    fresh_quiet = goldilocks_score({"age_hours": 2, "comments": 10})
    old_loud = goldilocks_score({"age_hours": 40, "comments": 5000})
    assert fresh_quiet > old_loud

def test_sort_latest():
    items = [_item("a", 30, 100, 3), _item("b", 2, 50, 25), _item("c", 10, 999, 99)]
    q = build_queue(items, drafts_map={}, commented=set(), sort="latest")
    assert [i["shortcode"] for i in q] == ["b", "c", "a"]

def test_sort_hot():
    items = [_item("a", 30, 100, 3), _item("b", 2, 50, 25), _item("c", 10, 999, 99)]
    q = build_queue(items, drafts_map={}, commented=set(), sort="hot")
    assert [i["shortcode"] for i in q] == ["c", "b", "a"]

def test_sort_goldilocks():
    items = [_item("fresh_quiet", 2, 10, 5), _item("old_loud", 40, 5000, 3)]
    q = build_queue(items, drafts_map={}, commented=set(), sort="goldilocks")
    assert q[0]["shortcode"] == "fresh_quiet"

def test_hide_done_filters_commented():
    items = [_item("a", 2, 10, 5), _item("b", 3, 20, 6)]
    q = build_queue(items, drafts_map={}, commented={"a"}, sort="latest", hide_done=True)
    assert [i["shortcode"] for i in q] == ["b"]

def test_show_done_marks_but_keeps():
    items = [_item("a", 2, 10, 5), _item("b", 3, 20, 6)]
    q = build_queue(items, drafts_map={}, commented={"a"}, sort="latest", hide_done=False)
    codes = {i["shortcode"]: i for i in q}
    assert set(codes) == {"a", "b"}
    assert codes["a"]["done"] is True
    assert codes["b"]["done"] is False

def test_drafts_attached():
    items = [_item("a", 2, 10, 5)]
    q = build_queue(items, drafts_map={"a": ["댓글1", "댓글2"]}, commented=set(), sort="latest")
    assert q[0]["drafts"] == ["댓글1", "댓글2"]
