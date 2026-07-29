import shopping_shorts.overseas_hot_jobs as job
from datetime import datetime, timezone


def test_run_collects_ranks_and_saves(monkeypatch, tmp_path):
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    published = "2026-07-25T12:00:00Z"

    def fake_tt(kw, max_results=40):
        return [{"video_id": "tt_" + kw, "title": kw + " kitchen gadget", "published_at": published,
                 "views": 500000, "likes": 900, "comments": 30, "collects": 0, "shares": 0,
                 "channel_title": "a", "thumbnail": "", "url": "https://tt", "media_platform": "tiktok"}]
    def fake_dy(kw, max_results=40):
        return [{"video_id": "dy_" + kw, "title": kw, "published_at": published,
                 "views": 0, "likes": 800, "comments": 20, "collects": 300, "shares": 10,
                 "channel_title": "b", "thumbnail": "", "url": "https://dy", "media_platform": "douyin"}]

    monkeypatch.setattr(job.tiktok_search, "search_full", fake_tt)
    monkeypatch.setattr(job.douyin_search, "search_full", fake_dy)
    monkeypatch.setattr(job.xiaohongshu_search, "search_full", lambda kw, max_results=40: [])
    monkeypatch.setattr(job.gap_check, "gap_badge", lambda title, **kw: "🔥선점가능")
    monkeypatch.setattr(job, "load_seeds",
                        lambda: {"주방/레시피": {"tiktok": ["kitchen"], "cn": ["厨房"]}})
    monkeypatch.setattr(job, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(job, "_now", lambda: now)

    job._run()
    from shopping_shorts.store import Store
    items, _ = Store(str(tmp_path / "t.db")).load_overseas_feed()
    assert items, "피드에 항목이 저장돼야 한다"
    assert all("grade" in it and it.get("category") == "주방/레시피" for it in items)
    assert {it["platform"] for it in items} == {"tiktok", "douyin"}
    assert items[0]["gap_badge"] == "🔥선점가능"


def test_run_purges_stale_categories(monkeypatch, tmp_path):
    # 폐기된 소스/카테고리(옛 레딧 만족감/신기템)가 피드에 눌러앉지 않고 퇴출돼야 한다.
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "t.db")
    from shopping_shorts.store import Store
    Store(db).save_overseas_feed([
        {"shortcode": "old1", "platform": "reddit", "category": "만족감/제품", "score": 0.9,
         "base_count": 0, "delta": 0, "gap_badge": "🔥선점가능"},
    ])

    def fake_tt(kw, max_results=40):
        return [{"video_id": "tt_new", "title": kw + " kitchen", "published_at": "2026-07-25T12:00:00Z",
                 "views": 100000, "likes": 500, "comments": 10, "collects": 0, "shares": 0,
                 "channel_title": "a", "thumbnail": "", "url": "https://tt", "media_platform": "tiktok"}]

    monkeypatch.setattr(job.tiktok_search, "search_full", fake_tt)
    monkeypatch.setattr(job.douyin_search, "search_full", lambda kw, max_results=40: [])
    monkeypatch.setattr(job.xiaohongshu_search, "search_full", lambda kw, max_results=40: [])
    monkeypatch.setattr(job.gap_check, "gap_badge", lambda title, **kw: "🔥선점가능")
    monkeypatch.setattr(job, "load_seeds", lambda: {"주방/레시피": {"tiktok": ["kitchen"], "cn": []}})
    monkeypatch.setattr(job, "DB_PATH", db)
    monkeypatch.setattr(job, "_now", lambda: now)

    job._run()
    items, _ = Store(db).load_overseas_feed()
    cats = {it.get("category") for it in items}
    assert "만족감/제품" not in cats, "폐기 카테고리는 퇴출돼야 한다"
    assert cats == {"주방/레시피"}


def test_start_is_idempotent_while_running(monkeypatch):
    monkeypatch.setattr(job, "_run", lambda: __import__("time").sleep(0.2))
    job._JOB.update(status="idle", started=0.0)
    r1 = job.start()
    r2 = job.start()
    assert r1["status"] == "running" and r2["status"] == "running"


def test_merge_rotate_dedupes_new_by_shortcode():
    # 같은 서브레딧이 여러 카테고리에 겹치면 같은 포스트가 중복 수집된다 →
    # shortcode당 score 최고 1개만 남아야 한다(UI·cap·스냅샷 중복 방지).
    new = [
        {"shortcode": "dup", "category": "살림/생활꿀템", "score": 0.2},
        {"shortcode": "dup", "category": "가전템", "score": 0.9},
        {"shortcode": "solo", "category": "뷰티", "score": 0.5},
    ]
    out = job._merge_rotate([], new, cap=120)
    ids = [i["shortcode"] for i in out]
    assert ids.count("dup") == 1 and "solo" in ids
    dup = next(i for i in out if i["shortcode"] == "dup")
    assert dup["score"] == 0.9   # score 최고가 남음


def test_collect_category_uses_playwright_crawl_when_xhs_scraper_set(monkeypatch):
    monkeypatch.setattr(job.config, "XHS_SCRAPER", "playwright")
    monkeypatch.setattr(job.douyin_search, "search_full", lambda kw, max_results=40: [])
    monkeypatch.setattr(job.xiaohongshu_search, "search_full",
                        lambda kw, max_results=40: (_ for _ in ()).throw(AssertionError("Apify 경로가 불렸다")))
    called = {}

    def fake_pw(kw, max_results=40):
        called["kw"] = kw
        return []

    monkeypatch.setattr(job.playwright_crawl, "search_full", fake_pw)

    class FakeStore:
        def prev_base_platform(self, *a, **k):
            return None

        def prev_delta_platform(self, *a, **k):
            return None

        def get_thumb_text_level(self, *a, **k):
            return None

        def save_thumb_text_level(self, *a, **k):
            pass

    job._collect_category("주방/레시피", {"tiktok": [], "cn": ["厨房神器"]}, FakeStore())
    assert called["kw"] == "厨房神器"


def test_collect_category_uses_apify_by_default(monkeypatch):
    monkeypatch.setattr(job.config, "XHS_SCRAPER", "apify")
    monkeypatch.setattr(job.douyin_search, "search_full", lambda kw, max_results=40: [])
    monkeypatch.setattr(job.playwright_crawl, "search_full",
                        lambda kw, max_results=40: (_ for _ in ()).throw(AssertionError("playwright 경로가 불렸다")))
    called = {}

    def fake_apify(kw, max_results=40):
        called["kw"] = kw
        return []

    monkeypatch.setattr(job.xiaohongshu_search, "search_full", fake_apify)

    class FakeStore:
        def prev_base_platform(self, *a, **k):
            return None

        def prev_delta_platform(self, *a, **k):
            return None

        def get_thumb_text_level(self, *a, **k):
            return None

        def save_thumb_text_level(self, *a, **k):
            pass

    job._collect_category("주방/레시피", {"tiktok": [], "cn": ["厨房神器"]}, FakeStore())
    assert called["kw"] == "厨房神器"


def test_annotate_text_level_marks_all_items(monkeypatch, tmp_path):
    # 2026-07-29: 상한(_TEXT_CLUTTER_CAP) 폐기 — 생존자 전부를 판정해야 한다.
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    monkeypatch.setattr(job.video_analysis, "fetch_thumb_bytes", lambda url, timeout=15: b"img")
    calls = []

    def fake_vision(img):
        calls.append(1)
        return {"text_level": "heavy"}

    monkeypatch.setattr(job.video_analysis, "text_level_vision", fake_vision)

    items = [{"shortcode": f"p{i}", "thumbnail": "http://x"} for i in range(5)]
    job._annotate_text_level(items, st)

    assert len(calls) == 5                          # 전부 판정
    assert items[0]["text_level"] == "heavy"
    assert items[4]["text_level"] == "heavy"


def test_collect_category_filters_out_heavy_text_thumbnails(monkeypatch):
    monkeypatch.setattr(job.douyin_search, "search_full", lambda kw, max_results=40: [])
    monkeypatch.setattr(job.xiaohongshu_search, "search_full", lambda kw, max_results=40: [])

    def fake_tt(kw, max_results=40):
        return [
            {"video_id": "clean1", "title": "kitchen gadget", "published_at": "2026-07-25T12:00:00Z",
             "views": 1000, "likes": 10, "comments": 1, "collects": 0, "shares": 0,
             "channel_title": "a", "thumbnail": "http://x/clean.jpg", "url": "https://tt/clean",
             "media_platform": "tiktok"},
            {"video_id": "cluttered1", "title": "kitchen gadget 2", "published_at": "2026-07-25T12:00:00Z",
             "views": 1000, "likes": 10, "comments": 1, "collects": 0, "shares": 0,
             "channel_title": "b", "thumbnail": "http://x/cluttered.jpg", "url": "https://tt/cluttered",
             "media_platform": "tiktok"},
        ]
    monkeypatch.setattr(job.tiktok_search, "search_full", fake_tt)
    monkeypatch.setattr(job.video_analysis, "fetch_thumb_bytes", lambda url, timeout=15: url.encode())

    def fake_vision(img):
        return {"text_level": "heavy" if b"cluttered" in img else "none"}

    monkeypatch.setattr(job.video_analysis, "text_level_vision", fake_vision)

    class FakeStore:
        def prev_base_platform(self, *a, **k):
            return None

        def prev_delta_platform(self, *a, **k):
            return None

        def get_thumb_text_level(self, *a, **k):
            return None

        def save_thumb_text_level(self, *a, **k):
            pass

    items = job._collect_category("주방/레시피", {"tiktok": ["kitchen"], "cn": []}, FakeStore())

    shortcodes = {i["shortcode"] for i in items}
    assert shortcodes == {"clean1"}                  # 자막 많은 cluttered1은 걸러짐


def test_collect_category_skips_tiktok_when_disabled(monkeypatch):
    monkeypatch.setattr(job.config, "OVERSEAS_TIKTOK_ENABLED", False)
    monkeypatch.setattr(job.tiktok_search, "search_full",
                        lambda kw, max_results=40: (_ for _ in ()).throw(AssertionError("틱톡이 불렸다")))
    monkeypatch.setattr(job.douyin_search, "search_full", lambda kw, max_results=40: [])
    monkeypatch.setattr(job.xiaohongshu_search, "search_full", lambda kw, max_results=40: [])

    class FakeStore:
        def prev_base_platform(self, *a, **k):
            return None

        def prev_delta_platform(self, *a, **k):
            return None

        def get_thumb_text_level(self, *a, **k):
            return None

        def save_thumb_text_level(self, *a, **k):
            pass

    job._collect_category("주방/레시피", {"tiktok": ["kitchen"], "cn": []}, FakeStore())  # 예외 없으면 통과


def test_collect_category_skips_douyin_when_disabled(monkeypatch):
    monkeypatch.setattr(job.config, "OVERSEAS_DOUYIN_ENABLED", False)
    monkeypatch.setattr(job.tiktok_search, "search_full", lambda kw, max_results=40: [])
    monkeypatch.setattr(job.douyin_search, "search_full",
                        lambda kw, max_results=40: (_ for _ in ()).throw(AssertionError("도우인이 불렸다")))
    monkeypatch.setattr(job.xiaohongshu_search, "search_full", lambda kw, max_results=40: [])

    class FakeStore:
        def prev_base_platform(self, *a, **k):
            return None

        def prev_delta_platform(self, *a, **k):
            return None

        def get_thumb_text_level(self, *a, **k):
            return None

        def save_thumb_text_level(self, *a, **k):
            pass

    job._collect_category("주방/레시피", {"tiktok": [], "cn": ["厨房神器"]}, FakeStore())  # 예외 없으면 통과


def test_add_pickup_saves_to_pickup_category(monkeypatch, tmp_path):
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(job.tiktok_search, "fetch_urls", lambda urls: [
        {"video_id": "p1", "title": "kitchen gadget", "published_at": "2020-01-01T00:00:00Z",
         "views": 100, "likes": 50, "comments": 5, "collects": 0, "shares": 0,
         "channel_title": "a", "thumbnail": "", "url": "https://tt/p1", "media_platform": "tiktok"}])
    monkeypatch.setattr(job.gap_check, "gap_badge", lambda t, **k: "🔥선점가능")
    monkeypatch.setattr(job, "load_seeds", lambda: {"주방/레시피": {"tiktok": ["kitchen"], "cn": []}})
    monkeypatch.setattr(job, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(job, "_now", lambda: now)
    added = job.add_pickup(["https://tt/p1"])
    assert added == 1
    from shopping_shorts.store import Store
    items, _ = Store(str(tmp_path / "t.db")).load_overseas_feed()
    assert items[0]["category"] == job.PICKUP_CATEGORY   # 픽업 카테고리로 저장
    assert items[0]["shortcode"] == "p1"                  # 2020년(오래된)도 window 우회로 생존


def _mk(sc, thumb="https://t/x.jpg"):
    return {"shortcode": sc, "thumbnail": thumb}


def test_annotate_judges_every_item_not_just_first_15(monkeypatch, tmp_path):
    """상한 폐기 — 20개를 주면 20개 다 판정돼야 한다(옛 _TEXT_CLUTTER_CAP=15 회귀)."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    monkeypatch.setattr(job.video_analysis, "fetch_thumb_bytes", lambda u: b"img")
    monkeypatch.setattr(job.video_analysis, "text_level_vision", lambda b: {"text_level": "none"})

    items = [_mk(f"s{i}") for i in range(20)]
    job._annotate_text_level(items, st)
    assert all(i["text_level"] == "none" for i in items)


def test_annotate_uses_cache_and_skips_vision(monkeypatch, tmp_path):
    """캐시에 있으면 비전을 부르지 않는다(쿼터 보호)."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    st.save_thumb_text_level("s1", "light")
    calls = []
    monkeypatch.setattr(job.video_analysis, "fetch_thumb_bytes", lambda u: b"img")
    monkeypatch.setattr(job.video_analysis, "text_level_vision",
                        lambda b: calls.append(1) or {"text_level": "none"})

    items = [_mk("s1")]
    job._annotate_text_level(items, st)
    assert items[0]["text_level"] == "light"   # 캐시값이 이긴다
    assert calls == [], "캐시 적중 시 비전 호출이 없어야 한다"


def test_annotate_saves_new_judgement_to_cache(monkeypatch, tmp_path):
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    monkeypatch.setattr(job.video_analysis, "fetch_thumb_bytes", lambda u: b"img")
    monkeypatch.setattr(job.video_analysis, "text_level_vision", lambda b: {"text_level": "heavy"})

    job._annotate_text_level([_mk("s1")], st)
    assert st.get_thumb_text_level("s1") == "heavy"


def test_annotate_does_not_cache_failure(monkeypatch, tmp_path):
    """판정 실패는 저장 안 한다 — 다음 수집에서 재시도돼야 한다."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    monkeypatch.setattr(job.video_analysis, "fetch_thumb_bytes", lambda u: b"img")
    monkeypatch.setattr(job.video_analysis, "text_level_vision", lambda b: {})

    items = [_mk("s1")]
    job._annotate_text_level(items, st)
    assert "text_level" not in items[0]
    assert st.get_thumb_text_level("s1") is None


def test_annotate_skips_when_no_thumbnail(monkeypatch, tmp_path):
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    monkeypatch.setattr(job.video_analysis, "fetch_thumb_bytes", lambda u: None)
    monkeypatch.setattr(job.video_analysis, "text_level_vision",
                        lambda b: {"text_level": "none"})

    items = [_mk("s1", thumb="")]
    job._annotate_text_level(items, st)
    assert "text_level" not in items[0]


def test_merge_rotate_puts_clean_thumbnails_first():
    """자막 없는 항목이 점수 높은 자막 항목보다 앞에 온다."""
    new = [
        {"shortcode": "dirty", "score": 0.9, "text_level": "light"},
        {"shortcode": "clean", "score": 0.1, "text_level": "none"},
    ]
    out = job._merge_rotate([], new, cap=10)
    assert [i["shortcode"] for i in out] == ["clean", "dirty"]


def test_merge_rotate_sorts_by_score_within_same_caption_rank():
    new = [
        {"shortcode": "lo", "score": 0.2, "text_level": "none"},
        {"shortcode": "hi", "score": 0.8, "text_level": "none"},
    ]
    out = job._merge_rotate([], new, cap=10)
    assert [i["shortcode"] for i in out] == ["hi", "lo"]


def test_merge_rotate_cap_keeps_clean_ones():
    """상한으로 자를 때도 자막 없는 것이 살아남는다."""
    new = [
        {"shortcode": "d1", "score": 0.9, "text_level": "light"},
        {"shortcode": "c1", "score": 0.1, "text_level": "none"},
    ]
    out = job._merge_rotate([], new, cap=1)
    assert [i["shortcode"] for i in out] == ["c1"]
