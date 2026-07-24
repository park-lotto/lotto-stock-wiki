from shopping_shorts.store import Store


def test_overseas_feed_roundtrip(tmp_path):
    db = str(tmp_path / "t.db")
    s = Store(db)
    assert s.load_overseas_feed() == ([], None)
    s.save_overseas_feed([{"shortcode": "aaa", "category": "뷰티", "speed": 1.0}])
    items, updated = s.load_overseas_feed()
    assert items[0]["shortcode"] == "aaa" and updated is not None
