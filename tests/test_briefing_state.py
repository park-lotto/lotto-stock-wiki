from briefing_state import load_state, save_state, reset_state, is_new_day


def test_reset_state_shape():
    st = reset_state("2026-07-06")
    assert st["date"] == "2026-07-06"
    assert st["turning_points"] == []
    assert st["verdict"] is None
    assert st["baseline"] is None


def test_save_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "w.json")
    st = reset_state("2026-07-06")
    st["verdict"] = {"tone": "🟢", "line": "테스트", "ts": "11:00"}
    save_state(p, st)
    got = load_state(p)
    assert got["verdict"]["line"] == "테스트"


def test_is_new_day():
    st = reset_state("2026-07-06")
    assert is_new_day(st, "2026-07-07") is True
    assert is_new_day(st, "2026-07-06") is False


def test_load_missing_returns_none(tmp_path):
    assert load_state(str(tmp_path / "nope.json")) is None
