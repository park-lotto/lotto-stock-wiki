from shopping_shorts import service


def test_collect_youtube(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(service, "preset_keywords", lambda categories=None: [])  # 프리셋 격리
    from shopping_shorts.store import Store
    Store(str(tmp_path / "t.db")).add_seed("youtube", "keyword", "살림꿀팁")

    def fake_search(keywords, published_after_iso, **kw):
        assert keywords == ["살림꿀팁"]
        return [{"video_id": "v1", "channel_title": "살림TV", "channel_id": "c1",
                 "title": "t", "thumbnail": "x",
                 "published_at": "2026-07-24T00:00:00Z",
                 "views": 24000, "likes": 100, "comments": 10}]
    monkeypatch.setattr(service, "yt_search", fake_search)

    items = service.collect(platform="youtube")
    assert len(items) == 1
    assert items[0]["platform"] == "youtube" and items[0]["base_count"] == 24000
    assert "grade" in items[0] and "score" in items[0]


def test_collect_youtube_merges_account_and_keyword(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(service, "preset_keywords", lambda categories=None: [])  # 프리셋 격리
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    st.add_seed("youtube", "keyword", "살림꿀팁")
    st.add_seed("youtube", "account", "@salim")

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
    assert ids == ["dup", "v1", "v2"]


def test_collect_youtube_preset_all(monkeypatch, tmp_path):
    # categories=None(전체 딸깍) → 프리셋 전 키워드가 lang=ko로 검색된다
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(service, "preset_keywords",
                        lambda categories=None: ["살림템", "메이크업"] if categories is None else [])
    seen = {}
    def fake_search(keywords, published_after_iso, **kw):
        seen["keywords"] = keywords
        seen["lang"] = kw.get("lang")
        return [{"video_id": "p1", "channel_title": "T", "channel_id": "c",
                 "title": "t", "thumbnail": "x",
                 "published_at": "2026-07-24T00:00:00Z",
                 "views": 500, "likes": 1, "comments": 0}]
    monkeypatch.setattr(service, "yt_search", fake_search)

    items = service.collect(platform="youtube")   # category 없음 = 전체
    assert seen["keywords"] == ["살림템", "메이크업"] and seen["lang"] == "ko"
    assert len(items) == 1 and items[0]["shortcode"] == "p1"


def test_collect_youtube_preset_scoped(monkeypatch, tmp_path):
    # categories=["혼합형"] → 그 카테고리 프리셋만
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(service, "preset_keywords",
                        lambda categories=None: ["뷰티꿀팁"] if categories == ["혼합형"] else ["WRONG"])
    seen = {}
    def fake_search(keywords, published_after_iso, **kw):
        seen["keywords"] = keywords
        return []
    monkeypatch.setattr(service, "yt_search", fake_search)

    service.collect(platform="youtube", categories=["혼합형"])
    assert seen["keywords"] == ["뷰티꿀팁"]
