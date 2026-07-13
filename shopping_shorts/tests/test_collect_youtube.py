from shopping_shorts import service


def test_collect_youtube(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "t.db"))
    from shopping_shorts.store import Store
    Store(str(tmp_path / "t.db")).add_seed("youtube", "keyword", "살림꿀팁")

    def fake_search(keywords, published_after_iso, **kw):
        assert keywords == ["살림꿀팁"]
        return [{"video_id": "v1", "channel_title": "살림TV", "channel_id": "c1",
                 "title": "t", "thumbnail": "x",
                 "published_at": "2026-07-12T00:00:00Z",
                 "views": 24000, "likes": 100, "comments": 10}]
    monkeypatch.setattr(service, "yt_search", fake_search)

    items = service.collect(platform="youtube")
    assert len(items) == 1
    assert items[0]["platform"] == "youtube" and items[0]["base_count"] == 24000
    assert "grade" in items[0] and "score" in items[0]
