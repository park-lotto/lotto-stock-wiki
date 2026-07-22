from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_enrichment_roundtrip_and_ttl(tmp_path):
    s = _store(tmp_path)
    data = {"channel_name": "채널", "subscribers": 100, "views": 9,
            "top_comments": [{"author": "A", "text": "c", "likes": 1}], "caption": "cap"}
    s.upsert_enrichment("http://u", "youtube", data, "ok", "2026-07-22T00:00:00")
    got = s.get_enrichment("http://u", max_age_days=7, now="2026-07-24T00:00:00")
    assert got["channel_name"] == "채널" and got["subscribers"] == 100
    assert got["top_comments"][0]["text"] == "c" and got["status"] == "ok"
    # 8일 지나면 만료 → None
    assert s.get_enrichment("http://u", max_age_days=7, now="2026-07-31T00:00:00") is None
    assert s.get_enrichment("http://none") is None
