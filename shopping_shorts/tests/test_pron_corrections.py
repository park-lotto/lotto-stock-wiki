"""전역 발음교정 사전(2026-07-22). 구절→재표기를 profile.pronunciation.dict에
병합해 모든 렌더에 적용. per-preset 명시 항목은 전역보다 우선(더 구체적)."""
from shopping_shorts import pron_corrections as pc


class FakeStore:
    def __init__(self, initial=None):
        self._kv = dict(initial or {})
    def get_setting(self, key, default=None):
        return self._kv.get(key, default)
    def set_setting(self, key, value):
        self._kv[key] = value


def test_save_then_load_roundtrip():
    s = FakeStore()
    pc.save(s, {"좋은데요": "조은데요"})
    assert pc.load(s) == {"좋은데요": "조은데요"}


def test_load_missing_returns_empty():
    assert pc.load(FakeStore()) == {}


def test_load_corrupt_returns_empty():
    assert pc.load(FakeStore({"global_pron_dict": "{not json"})) == {}


def test_overlay_merges_global_into_profile():
    prof = {"pronunciation": {"on": True, "dict": {}}}
    out = pc.overlay(prof, {"좋은데요": "조은데요"})
    assert out["pronunciation"]["dict"]["좋은데요"] == "조은데요"
    assert prof["pronunciation"]["dict"] == {}          # 원본 불변


def test_overlay_per_preset_wins_on_collision():
    prof = {"pronunciation": {"on": True, "dict": {"AS": "에이에스(프리셋)"}}}
    out = pc.overlay(prof, {"AS": "에이에스(전역)"})
    assert out["pronunciation"]["dict"]["AS"] == "에이에스(프리셋)"


def test_overlay_empty_global_returns_profile_unchanged():
    prof = {"pronunciation": {"on": True, "dict": {}}}
    assert pc.overlay(prof, {}) is prof


def test_overlay_creates_pronunciation_when_absent():
    out = pc.overlay({}, {"좋은데요": "조은데요"})
    assert out["pronunciation"]["dict"] == {"좋은데요": "조은데요"}
