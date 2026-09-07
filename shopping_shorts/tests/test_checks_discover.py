import sqlite3
from shopping_shorts.checks import discover, ro


def test_discover_health_returns_only_modules_with_meta():
    mods = discover.discover("health")
    assert all(hasattr(m, "META") and "name" in m.META and "every" in m.META for m in mods)
    assert all(m.__name__.rsplit(".", 1)[-1].startswith("h_") for m in mods)


def test_is_due_parses_every():
    assert discover.is_due("1h", None) is True
    assert discover.is_due("1h", "2026-09-07T00:00:00+00:00", now="2026-09-07T00:30:00+00:00") is False
    assert discover.is_due("1h", "2026-09-07T00:00:00+00:00", now="2026-09-07T01:00:01+00:00") is True


def test_ro_connect_refuses_writes(tmp_path):
    p = tmp_path / "live.db"
    sqlite3.connect(p).execute("CREATE TABLE t(x)").connection.commit()
    conn = ro.ro_connect(p)
    try:
        conn.execute("INSERT INTO t VALUES(1)")
        assert False, "쓰기가 됐다"
    except sqlite3.OperationalError:
        pass
