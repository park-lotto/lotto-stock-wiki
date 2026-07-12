from shopping_shorts.store import Store


def test_set_and_get_setting(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert s.get_setting("vmake_api_key") is None      # 기본 None
    s.set_setting("vmake_api_key", "abc123")
    assert s.get_setting("vmake_api_key") == "abc123"


def test_set_setting_overwrites(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("vmake_api_key", "first")
    s.set_setting("vmake_api_key", "second")
    assert s.get_setting("vmake_api_key") == "second"


def test_get_setting_default(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert s.get_setting("missing", default="fallback") == "fallback"
