from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_list_pattern_sources_filters_category_source(tmp_path):
    s = _store(tmp_path)
    a = s.add_pattern_source("crawl", "u1", "글A", product_category="레시피", category_source="gemini")
    b = s.add_pattern_source("crawl", "u2", "글B", product_category="레시피", category_source="keyword")
    ids = {r["id"] for r in s.list_pattern_sources(category_source=("user", "gemini"))}
    assert a in ids and b not in ids


def test_set_source_perf_and_spine(tmp_path):
    s = _store(tmp_path)
    sid = s.add_pattern_source("crawl", "u", "글")
    s.set_pattern_source_perf(sid, {"platform": "tiktok", "views": 1000, "likes": 50})
    s.set_pattern_source_spine(sid, 7)
    row = [r for r in s.list_pattern_sources() if r["id"] == sid][0]
    assert row["perf"]["views"] == 1000 and row["spine_id"] == 7


def test_pattern_source_url_exists(tmp_path):
    s = _store(tmp_path)
    s.add_pattern_source("crawl", "http://x/1", "글")
    assert s.pattern_source_url_exists("http://x/1") is True
    assert s.pattern_source_url_exists("http://x/2") is False
    assert s.pattern_source_url_exists("") is False


def test_set_item_perf_and_update_spine_stats(tmp_path):
    s = _store(tmp_path)
    iid = s.add_pattern_item("hook", "이거 아세요?")
    s.set_pattern_item_perf(iid, 0.87)
    assert s.list_pattern_items(bucket="hook")[0]["perf_score"] == 0.87
    sp = s.add_spine("의심→인정", situation_type="레시피")
    s.update_spine_stats(sp, source_count=3, perf_score=0.5)
    row = [r for r in s.list_spines() if r["id"] == sp][0]
    assert row["source_count"] == 3 and row["perf_score"] == 0.5


def test_list_pattern_sources_only_missing_spine(tmp_path):
    s = _store(tmp_path)
    a = s.add_pattern_source("crawl", "u1", "글A")
    b = s.add_pattern_source("crawl", "u2", "글B")
    s.set_pattern_source_spine(b, 5)
    ids = {r["id"] for r in s.list_pattern_sources(only_missing_spine=True)}
    assert a in ids and b not in ids
