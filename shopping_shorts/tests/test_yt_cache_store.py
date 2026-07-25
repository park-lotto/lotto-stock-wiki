from shopping_shorts.store import Store


def test_yt_cache_roundtrip(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert s.yt_cache_get("@handle") is None          # 미해석은 None
    s.yt_cache_put("@handle", "UCabc", "UUabc")
    assert s.yt_cache_get("@handle") == ("UCabc", "UUabc")


def test_yt_cache_put_overwrites(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.yt_cache_put("@h", "UC1", "UU1")
    s.yt_cache_put("@h", "UC2", "UU2")               # 같은 seed 재해석 시 갱신
    assert s.yt_cache_get("@h") == ("UC2", "UU2")
