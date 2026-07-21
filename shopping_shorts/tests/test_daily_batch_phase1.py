from shopping_shorts import daily_batch as db
from shopping_shorts.store import Store


# ---- Task 5: ingest_crawl_winners ----
class _FakeStore:
    def __init__(self):
        self._urls = set()

    def load_last_run_platform(self, platform):
        if platform != "tiktok":
            return [], None
        return ([{"shortcode": "SC1", "grade": "S", "url": "http://t/1", "platform": "tiktok",
                  "views": 900, "likes": 80, "comments": 5},
                 {"shortcode": "SC2", "grade": "B", "url": "http://t/2", "platform": "tiktok",
                  "views": 3, "likes": 0, "comments": 0}], "2026-07-21T00:00:00")

    def wiki_list(self, *a, **k):
        return [{"shortcode": "SC1", "full_text": "우승 대본", "category_source": "gemini",
                 "category": "레시피"}]

    def pattern_source_url_exists(self, url):
        return url in self._urls


def test_ingest_crawl_winners_only_s_grade_with_script():
    fs = _FakeStore()
    captured = {}

    def fake_ingest(store, full_text, **kw):
        captured.update(kw)
        captured["full_text"] = full_text
        fs._urls.add(kw["url"])
        return {"source_id": 1, "added": 0}

    n = db.ingest_crawl_winners(fs, platforms=("tiktok",),
                                ingest_fn=fake_ingest, call=lambda *a, **k: {})
    assert n == 1
    assert captured["url"] == "http://t/1"
    assert captured["perf"]["views"] == 900
    assert captured["category_source"] == "gemini"


def test_ingest_crawl_winners_dedups():
    fs = _FakeStore()
    fs._urls.add("http://t/1")
    n = db.ingest_crawl_winners(fs, platforms=("tiktok",),
                                ingest_fn=lambda *a, **k: {"source_id": 1, "added": 0})
    assert n == 0


# ---- Task 7: recompute_perf_scores ----
def test_recompute_perf_scores_sets_item_from_source(tmp_path):
    s = Store(str(tmp_path / "p.db"))
    hi = s.add_pattern_source("crawl", "u1", "A", product_category="레시피",
                              category_source="gemini",
                              perf={"platform": "tiktok", "views": 100000, "likes": 9000,
                                    "comments": 300, "followers": None,
                                    "captured_at": "2026-07-21T00:00:00"})
    lo = s.add_pattern_source("crawl", "u2", "B", product_category="레시피",
                              category_source="gemini",
                              perf={"platform": "tiktok", "views": 5, "likes": 0,
                                    "comments": 0, "followers": None,
                                    "captured_at": "2026-07-21T00:00:00"})
    hi_item = s.add_pattern_item("hook", "대박 훅", source_id=hi)
    lo_item = s.add_pattern_item("hook", "밋밋 훅", source_id=lo)
    n = db.recompute_perf_scores(s, now_iso="2026-07-21T00:00:00")
    assert n >= 2
    items = {i["id"]: i["perf_score"] for i in s.list_pattern_items(bucket="hook")}
    assert items[hi_item] > items[lo_item]


# ---- Task 9: cluster_and_gate_spines ----
def test_cluster_and_gate_creates_pending_and_counts(tmp_path):
    s = Store(str(tmp_path / "c.db"))
    ids = []
    for i in range(3):
        ids.append(s.add_pattern_source("crawl", f"u{i}", f"글{i}", product_category="레시피",
                   category_source="gemini",
                   perf={"platform": "tiktok", "views": 100, "likes": 5, "comments": 1,
                         "followers": None, "captured_at": "2026-07-21T00:00:00"}))

    def fake_call(prompt, schema):
        return {"assignments": [{"source_id": sid, "spine_name": "__NEW__",
                                 "situation_type": "제3자의심→인정"} for sid in ids]}

    r = db.cluster_and_gate_spines(s, call=fake_call, now_iso="2026-07-21T00:00:00")
    assert r["new_spines"] == 1 and r["assigned"] == 3
    sp = s.list_spines()[0]
    assert sp["status"] == "pending"        # 게이트: 자동승인 금지
    assert sp["source_count"] == 3
    src = [x for x in s.list_pattern_sources() if x["id"] == ids[0]][0]
    assert src["spine_id"] == sp["id"]


# ---- Task 10: run wiring ----
def test_run_calls_all_steps(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(db, "backfill_structures", lambda s, *a, **k: calls.append("bf") or 0)
    monkeypatch.setattr(db, "recompute_element_stats", lambda s, *a, **k: calls.append("es") or 0)
    monkeypatch.setattr(db, "ingest_crawl_winners", lambda s, *a, **k: calls.append("iw") or 0)
    monkeypatch.setattr(db, "recompute_perf_scores", lambda s, *a, **k: calls.append("ps") or 0)
    monkeypatch.setattr(db, "cluster_and_gate_spines",
                        lambda s, *a, **k: calls.append("cs") or {"assigned": 0, "new_spines": 0})
    db.run(str(tmp_path / "r.db"))
    assert calls == ["bf", "es", "iw", "ps", "cs"]
