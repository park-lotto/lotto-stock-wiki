from shopping_shorts.bank_assemble import bank_usage_snapshot


class FakeStore:
    def __init__(self, enabled="1", spine=None, items=None, recent=None):
        self._enabled = enabled
        self._spine = spine
        self._items = items or {}   # bucket -> list of item dicts
        self._recent = recent or {"hooks": [], "persons": [], "ctas": []}

    def get_setting(self, key, default=None):
        return self._enabled if key == "bank_enabled" else default

    def pick_spine_for_category(self, category, status="approved", min_sources=3):
        return self._spine

    def list_pattern_items(self, bucket=None, status=None, order_by=None, limit=None):
        return list(self._items.get(bucket, []))

    def recent_script_usage(self, limit=8):
        return self._recent


def test_snapshot_empty_when_no_spine_no_parts():
    snap = bank_usage_snapshot(FakeStore(spine=None, items={}), "recipe")
    assert snap["spine_present"] is False
    assert snap["parts_total"] == 0
    assert snap["empty"] is True
    assert snap["category"] == "recipe"


def test_snapshot_filled_when_spine_and_parts():
    spine = {"beat_chain": ["a", "b", "c"], "situation_type": "x"}
    items = {"hook": [{"text": "h1"}, {"text": "h2"}], "cta": [{"text": "c1"}]}
    recent = {"hooks": ["old"], "persons": [], "ctas": []}
    snap = bank_usage_snapshot(FakeStore(spine=spine, items=items, recent=recent), "recipe")
    assert snap["spine_present"] is True
    assert snap["spine_beats"] == 3
    assert snap["parts_by_bucket"]["hook"] == 2
    assert snap["parts_total"] == 3
    assert snap["avoid_present"] is True
    assert snap["empty"] is False


def test_snapshot_disabled_flag():
    snap = bank_usage_snapshot(FakeStore(enabled=""), "recipe")
    assert snap["bank_enabled"] is False
