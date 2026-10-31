# -*- coding: utf-8 -*-
"""숏클 결제 상품 표 _pay_products(관제 292) — 금액은 서버 표에서만, 11월 차액은 숏템 회원만."""
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts.store import Store

NOV = datetime(2026, 11, 30, 14, 59, tzinfo=timezone.utc)    # 한국 11-30 23:59
DEC = datetime(2026, 11, 30, 15, 0, tzinfo=timezone.utc)     # 한국 12-01 00:00


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", path)
    monkeypatch.setenv("TOSS_CLIENT_KEY", "test_ck")
    monkeypatch.setenv("TOSS_SECRET_KEY", "test_sk")
    monkeypatch.setattr(appmod, "_shortcl_upgrade_open", lambda now=None: True)
    Store(path)
    return TestClient(appmod.app)


def _order(client, product, cookies=None):
    for k, v in (cookies or {}).items():
        client.cookies.set(k, v)
    return client.post("/api/pay/toss/order", json={"name": "홍길동", "phone": "010", "email": "a@b.co",
                                                    "product": product})


def test_금액표가_사장님_결정과_같다(client):
    got = {p["code"]: p["amount"] for p in appmod._pay_products()}
    assert got == {"shortem": 880000, "shortcl_basic": 990000, "shortcl_advanced": 1990000,
                   "shortcl_premium": 2990000, "shortcl_basic_upgrade": 110000,
                   "shortcl_advanced_upgrade": 1110000, "shortcl_premium_upgrade": 2110000}


def test_차액은_한국시각_11월_30일까지만(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    Store(str(tmp_path / "t.db"))
    assert appmod._pay_product("shortcl_basic_upgrade", NOV)
    assert appmod._pay_product("shortcl_basic_upgrade", DEC) is None
    assert appmod._pay_product("shortcl_basic", DEC)


def test_주문은_상품_금액을_서버가_정하고_코드를_남긴다(client):
    r = client.post("/api/pay/toss/order", json={"name": "a", "phone": "1", "email": "a@b.co",
                                                 "product": "shortcl_premium", "amount": 1})
    assert r.status_code == 200 and r.json()["amount"] == 2990000
    with appmod._toss_db()._conn() as c:
        assert c.execute("SELECT product, amount FROM toss_payments").fetchone() == ("shortcl_premium", 2990000)


def test_상품을_안_보내면_기존_숏템_주문(client):
    r = client.post("/api/pay/toss/order", json={"name": "a", "phone": "1", "email": "a@b.co"})
    assert r.json()["amount"] == 880000


def test_없는_상품은_거절(client):
    assert _order(client, "shortcl_free").status_code == 422
    assert client.get("/pay/toss?product=shortcl_free", follow_redirects=False).status_code == 404


def test_차액은_비로그인_거절(client):
    assert _order(client, "shortcl_basic_upgrade").status_code == 401
    assert client.get("/pay/toss?product=shortcl_basic_upgrade", follow_redirects=False).status_code == 401


def test_차액은_무료회원_거절_프로회원_통과(client, monkeypatch):
    monkeypatch.setattr(appmod, "_verify_session", lambda c: 7)
    store = Store(appmod.DB_PATH)
    monkeypatch.setattr(Store, "get_customer", lambda self, cid: {"plan": "free"})
    assert _order(client, "shortcl_basic_upgrade").status_code == 403
    monkeypatch.setattr(Store, "get_customer", lambda self, cid: {"plan": "pro"})
    r = _order(client, "shortcl_basic_upgrade")
    assert r.status_code == 200 and r.json()["amount"] == 110000
    with store._conn() as c:
        assert c.execute("SELECT product, customer_id FROM toss_payments").fetchone() == ("shortcl_basic_upgrade", "7")


def test_입금_신고에_상품이_남는다(client):
    r = client.post("/api/deposit_claim", json={"name": "a", "depositor": "b", "product": "shortcl_advanced"})
    assert r.status_code == 200
    assert Store(appmod.DB_PATH).list_deposit_claims()[0]["product"] == "숏클메이커 고급반"


def test_화면에_숏클_금액이_보인다(client):
    Store(appmod.DB_PATH).set_setting("bank_account", "123")
    pay = client.get("/pay").text
    pricing = client.get("/pricing").text
    for amount in ("990,000원", "1,990,000원", "2,990,000원", "110,000원", "1,110,000원", "2,110,000원"):
        assert amount in pay, amount
    assert "1,990,000" in pricing and "__SHORTCL_PLANS__" not in pricing
    assert "__PRODUCT_OPTIONS__" not in pay
    toss = client.get("/pay/toss?product=shortcl_basic").text
    assert "숏클메이커 기본반" in toss and "Claude Max" in toss and appmod._SHORTCL_FORM_URL in toss


def test_맨위_숏클_출시_띠(client):
    for html in (appmod._with_pay(appmod._LANDING_HTML), client.get("/pricing").text):
        assert "__SHORTCL_BANNER__" not in html
        assert html.index("숏클메이커 출시") < html.index("<div class=nav>")


def test_대문_상단_출시영역과_숏클_안내(client):
    html = appmod._with_pay(appmod._LANDING_HTML)
    assert "__SHORTCL_PRICES__" not in html and "__SHORTCL_FROM__" not in html
    assert html.index("<div class=nav>") < html.index("class=sc-title") < html.index("<div class=hook>")
    assert "기본반 990,000원부터" in html
    assert "2,990,000원" in html and "Claude Max" in html
    landing = Path(appmod.__file__).parent / "static" / "landing"
    for name in re.findall(r"data-video=(sc_\w+)", html):
        assert (landing / f"{name}.mp4").exists() and (landing / f"{name}.jpg").exists(), name
    pricing = client.get("/pricing").text
    assert "__PRO_PERIOD__" not in pricing and "숏클메이커는 무엇이 필요한가요?" in pricing
    assert "이용기간: 라이선스 키 발급일" in client.get("/pay/toss?product=shortcl_basic").text
    assert "이용기간: 라이선스 키 발급일" not in client.get("/pay/toss").text
