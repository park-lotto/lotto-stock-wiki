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


def test_collect_youtube_merges_account_and_keyword(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "t.db"))
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    st.add_seed("youtube", "keyword", "살림꿀팁")        # 키워드 시드
    st.add_seed("youtube", "account", "@salim")         # 계정 시드

    # 키워드 경로: v1 + 겹치는 dup
    def fake_search(keywords, published_after_iso, **kw):
        return [
            {"video_id": "v1", "channel_title": "A", "channel_id": "c1", "title": "t",
             "thumbnail": "x", "published_at": "2026-07-24T00:00:00Z",
             "views": 1000, "likes": 5, "comments": 1},
            {"video_id": "dup", "channel_title": "A", "channel_id": "c1", "title": "t",
             "thumbnail": "x", "published_at": "2026-07-24T00:00:00Z",
             "views": 1000, "likes": 5, "comments": 1},
        ]
    monkeypatch.setattr(service, "yt_search", fake_search)

    # 계정 경로: v2 + 겹치는 dup(같은 video_id → 1개로 합쳐져야)
    def fake_channel(seed, **kw):
        assert seed == "@salim"
        return [
            {"video_id": "v2", "channel_title": "B", "channel_id": "c2", "title": "t",
             "thumbnail": "x", "published_at": "2026-07-24T00:00:00Z",
             "views": 2000, "likes": 9, "comments": 3},
            {"video_id": "dup", "channel_title": "B", "channel_id": "c2", "title": "t",
             "thumbnail": "x", "published_at": "2026-07-24T00:00:00Z",
             "views": 2000, "likes": 9, "comments": 3},
        ]
    monkeypatch.setattr(service, "yt_fetch_channel", fake_channel)

    items = service.collect(platform="youtube")
    ids = sorted(i["shortcode"] for i in items)
    assert ids == ["dup", "v1", "v2"]                   # dup 중복제거 → 3개
