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


def test_create_customer_stores_name_phone(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u1", "pw12", name="홍길동", phone="010-1234-5678")
    cust = s.get_customer(cid)
    assert cust["name"] == "홍길동" and cust["phone"] == "010-1234-5678"


def test_add_and_list_payments(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u2", "pw12")
    p1 = s.add_payment(cid, 30000, "계좌이체", 30, paid_at=1000, note="1월")
    s.add_payment(cid, 30000, "카드", 30, paid_at=2000)
    assert p1["amount"] == 30000 and p1["period_days"] == 30
    rows = s.list_payments(cid)
    assert len(rows) == 2
    assert rows[0]["paid_at"] == 2000   # 최신 먼저
    assert rows[1]["method"] == "계좌이체"


def test_approve_sets_start_end_and_payment(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pend", "pw12", approved=False)
    with s._conn() as conn:                      # 체험창 만료 강제 → 진짜 pending 상태로 검증
        conn.execute("UPDATE customers SET trial_ends_at=NULL WHERE id=?", (cid,))
    assert appmod.access_level(cid) == "pending"
    cust = s.approve_customer(cid, period_days=30, amount=30000, method="계좌이체")
    assert cust["approved_at"] is not None                 # 시작일
    assert cust["full_access_until"] > cust["approved_at"] # 마감일 미래
    assert appmod.access_level(cid) == "full"
    assert len(s.list_payments(cid)) == 1


def test_reapprove_extends_and_keeps_start(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pend2", "pw12", approved=False)
    c1 = s.approve_customer(cid, period_days=30, amount=30000, method="계좌")
    start1, end1 = c1["approved_at"], c1["full_access_until"]
    c2 = s.approve_customer(cid, period_days=30, amount=30000, method="계좌")
    assert c2["approved_at"] == start1          # 시작일 불변
    assert c2["full_access_until"] >= end1 + 30 * 86400 - 5   # 만료일 뒤로 연장(±오차)
    assert len(s.list_payments(cid)) == 2       # 결제 2건 누적


def test_admin_approve_with_payment(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("pend", "pw12", approved=False)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.post("/api/admin/approve",
                   json={"customer_id": cid, "period_days": 30, "amount": 30000, "method": "계좌"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert appmod.access_level(cid) == "full"
    assert len(s.list_payments(cid)) == 1


def test_admin_payment_extends(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u", "pw12", approved=False)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    owner.post("/api/admin/approve", json={"customer_id": cid, "period_days": 30, "amount": 30000, "method": "계좌"})
    end1 = s.get_customer(cid)["full_access_until"]
    r = owner.post("/api/admin/payment", json={"customer_id": cid, "period_days": 30, "amount": 30000, "method": "카드"})
    assert r.status_code == 200
    assert s.get_customer(cid)["full_access_until"] > end1
    assert len(s.list_payments(cid)) == 2


def test_admin_payments_list(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u", "pw12", approved=False)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    owner.post("/api/admin/approve", json={"customer_id": cid, "period_days": 30, "amount": 30000, "method": "계좌"})
    r = owner.get(f"/api/admin/payments?customer_id={cid}")
    assert r.status_code == 200 and len(r.json()["payments"]) == 1


def test_admin_customers_has_name_phone_and_last_payment(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("u", "pw12", approved=False, name="김철수", phone="010-0000-0000")
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    owner.post("/api/admin/approve", json={"customer_id": cid, "period_days": 30, "amount": 30000, "method": "계좌"})
    row = [c for c in owner.get("/api/admin/customers").json()["customers"] if c["id"] == cid][0]
    assert row["name"] == "김철수" and row["phone"] == "010-0000-0000"
    assert row["last_payment"]["amount"] == 30000 and row["payment_count"] == 1


def test_signup_stores_name_phone(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    c = TestClient(appmod.app, follow_redirects=False)
    c.post("/api/signup", data={"user": "newby", "pass": "pw12345", "name": "이영희", "phone": "010-1111-2222"})
    with s._conn() as conn:
        row = conn.execute("SELECT name, phone FROM customers WHERE username='newby'").fetchone()
    assert row is not None and row[0] == "이영희" and row[1] == "010-1111-2222"
