import types
import sqlite3
from shopping_shorts.checks import discover, ro


class _FakeInfo:
    def __init__(self, name):
        self.name = name


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


def test_discover_skips_broken_module_but_records_it(monkeypatch, caplog):
    real_import = importlib_import_module = discover.importlib.import_module
    good = types.SimpleNamespace(META={"name": "good", "every": "1h"})

    monkeypatch.setattr(
        discover.pkgutil, "iter_modules",
        lambda path: [_FakeInfo("h_bad"), _FakeInfo("h_good")],
    )

    def fake_import(name):
        if name.endswith(".h_bad"):
            raise ValueError("일부러 깨진 모듈")
        if name.endswith(".h_good"):
            return good
        return real_import(name)

    monkeypatch.setattr(discover.importlib, "import_module", fake_import)

    with caplog.at_level("WARNING"):
        mods = discover.discover("health")

    assert mods == [good]
    assert any(name.endswith("h_bad") for name, _ in discover.LAST_ERRORS)
    assert len(discover.LAST_ERRORS) == 1
    assert any("h_bad" in rec.message for rec in caplog.records)


def test_last_errors_empty_when_all_ok(monkeypatch):
    real_import = discover.importlib.import_module
    good = types.SimpleNamespace(META={"name": "good", "every": "1h"})

    monkeypatch.setattr(
        discover.pkgutil, "iter_modules",
        lambda path: [_FakeInfo("h_good")],
    )

    def fake_import(name):
        if name.endswith(".h_good"):
            return good
        return real_import(name)

    monkeypatch.setattr(discover.importlib, "import_module", fake_import)

    mods = discover.discover("health")

    assert mods == [good]
    assert discover.LAST_ERRORS == []
