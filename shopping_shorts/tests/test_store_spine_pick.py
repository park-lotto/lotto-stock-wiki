from shopping_shorts.store import Store


def test_pick_spine_respects_gate(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    a = s.add_spine("맞음", situation_type="레시피", fit_categories=["레시피"], status="approved")
    s.update_spine_stats(a, source_count=3, perf_score=0.8)
    b = s.add_spine("소스부족", fit_categories=["레시피"], status="approved")
    s.update_spine_stats(b, source_count=2, perf_score=0.99)
    c = s.add_spine("미승인", fit_categories=["레시피"], status="pending")
    s.update_spine_stats(c, source_count=5, perf_score=0.99)
    picked = s.pick_spine_for_category("레시피")
    assert picked is not None and picked["id"] == a


def test_pick_spine_none_when_no_match(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    a = s.add_spine("딴카테", fit_categories=["뷰티"], status="approved")
    s.update_spine_stats(a, source_count=3, perf_score=0.8)
    assert s.pick_spine_for_category("레시피") is None


def test_pick_spine_empty_fit_categories_matches_any(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    a = s.add_spine("범용", situation_type="공통", status="approved")  # fit_categories 없음
    s.update_spine_stats(a, source_count=4, perf_score=0.5)
    picked = s.pick_spine_for_category("레시피")
    assert picked is not None and picked["id"] == a
