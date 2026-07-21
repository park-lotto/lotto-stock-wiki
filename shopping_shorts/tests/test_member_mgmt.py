from datetime import datetime, timezone
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _cookie(cid):
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(cid, exp)


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    return s


def test_schema_has_name_phone_and_payments(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    with s._conn() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(customers)").fetchall()}
        assert "name" in cols and "phone" in cols
        pcols = {r[1] for r in c.execute("PRAGMA table_info(payments)").fetchall()}
    assert {"id", "customer_id", "amount", "method", "period_days", "paid_at", "note", "created_at"} <= pcols
