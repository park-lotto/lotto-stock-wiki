from shopping_shorts import perf_score, pattern_bank
from shopping_shorts.store import Store


def test_perf_from_item_tiktok():
    p = perf_score.perf_from_item({"platform": "tiktok", "views": 900, "likes": 80,
                                    "comments": 5, "followers": None})
    assert p["views"] == 900 and p["likes"] == 80 and p["comments"] == 5
    assert p["followers"] is None  # tiktok has no followers
    assert p["platform"] == "tiktok"


def test_perf_from_item_missing_keys_are_none():
    p = perf_score.perf_from_item({"platform": "xiaohongshu", "views": 10, "likes": 2})
    assert p["comments"] is None and p["followers"] is None


def test_ingest_script_stores_perf(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    fake = lambda prompt, schema: {"hook": ["훅"], "ending": [], "adverb": [], "cta": [],
                                    "price": [], "evidence": [], "conflict": [], "emotion": [],
                                    "spine": {}}
    r = pattern_bank.ingest_script(s, "본문", source="crawl", url="u1",
                                   product_category="레시피", category_source="gemini",
                                   perf={"platform": "tiktok", "views": 900}, call=fake)
    src = [x for x in s.list_pattern_sources() if x["id"] == r["source_id"]][0]
    assert src["perf"]["views"] == 900 and src["category_source"] == "gemini"
