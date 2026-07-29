"""해외HOT 썸네일 자막등급 캐시(2026-07-29) — 비전 재호출을 막는다."""
from shopping_shorts.store import Store


def test_get_returns_none_when_never_saved(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    assert st.get_thumb_text_level("sc1") is None


def test_save_and_get_roundtrip(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_thumb_text_level("sc1", "none")
    assert st.get_thumb_text_level("sc1") == "none"


def test_save_overwrites_same_shortcode(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_thumb_text_level("sc1", "light")
    st.save_thumb_text_level("sc1", "heavy")
    assert st.get_thumb_text_level("sc1") == "heavy"
