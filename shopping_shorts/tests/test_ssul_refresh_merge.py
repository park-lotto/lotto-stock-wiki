"""merge_last_run_platform(update_existing=True) — 썰쇼핑 3시간 갱신의 저장 계약."""
import json

from shopping_shorts.store import Store


def _load(store):
    d = json.loads(store.get_setting("last_run::youtube"))
    return {i["shortcode"]: i for i in d["items"]}, d["collected_at"]


def test_update_existing_replaces_and_rebases_age(tmp_path):
    store = Store(tmp_path / "t.db")
    t0 = "2026-09-14T00:00:00+00:00"
    t3 = "2026-09-14T03:00:00+00:00"
    store.save_last_run_platform("youtube", [
        {"shortcode": "old", "views": 10, "age_hours": 5.0, "delta": 0},
        {"shortcode": "keep", "views": 7, "age_hours": 20.0, "delta": 0},
    ], t0)
    store.merge_last_run_platform("youtube", [
        {"shortcode": "old", "views": 99, "age_hours": 8.0, "delta": 1},
        {"shortcode": "new", "views": 3, "age_hours": 1.0, "delta": 3},
    ], t3, update_existing=True)
    items, at = _load(store)
    assert at == t3
    assert items["old"]["views"] == 99 and items["old"]["age_hours"] == 8.0   # 교체
    assert items["keep"]["age_hours"] == 23.0                                  # +3h 보정
    assert "new" in items


def test_default_merge_unchanged(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_last_run_platform("pinterest", [
        {"shortcode": "a", "views": 1, "age_hours": 5.0, "delta": 0}], "2026-09-14T00:00:00+00:00")
    store.merge_last_run_platform("pinterest", [
        {"shortcode": "a", "views": 50, "delta": 0}], "2026-09-14T03:00:00+00:00")
    d = json.loads(store.get_setting("last_run::pinterest"))
    a = [i for i in d["items"] if i["shortcode"] == "a"][0]
    assert a["views"] == 1 and a["age_hours"] == 5.0
