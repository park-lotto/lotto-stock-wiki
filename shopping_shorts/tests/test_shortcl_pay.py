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


def test_숏클_요금탭에_숏템_내용이_섞이지_않는다(client):
    html = client.get("/pricing").text
    view = html[html.index("data-pv=shortcl id=shortcl"):html.index("<div class=foot>")]
    for word in ("레퍼런스", "랭킹", "렌즈", "보이스", "하루 10개", "무료 체험", "880,000"):
        assert word not in view, word
    assert "자주 묻는 질문" in view and "2,990,000" in view
    assert "무료로 레퍼런스 랭킹부터" not in html


def test_숏클_결제창_안내문은_숏클_이름(client):
    html = client.get("/pay/toss?product=shortcl_basic").text
    assert "숏클메이커는 영상 제작을" in html
    box = html[:html.index("환불정책 전문")]
    assert "숏템메이커는 영상 제작을" not in box


@pytest.mark.parametrize("code,form_key", [("shortem", "숏템"), ("shortcl_basic", "숏클"), ("shortcl_advanced", "숏클"),
                                           ("shortcl_premium", "숏클")])
def test_상품별_결제창이_제_상품으로_이어진다(client, code, form_key):
    prod = appmod._pay_product(code)
    html = client.get(appmod._pay_href(prod)).text
    assert f"<div class=amt>{prod['amount']:,}원</div>" in html and prod["name"] in html
    is_shortem = form_key == "숏템"
    assert (appmod._APPLY_FORM_URL in html) is is_shortem
    assert (appmod._SHORTCL_FORM_URL in html) is not is_shortem
    assert ("이용기간: 라이선스 키 발급일" in html) is not is_shortem
    assert ("Claude Max 구독(별도 결제)이 필요합니다" in html) is not is_shortem
    assert f'"product": "{code}"'.replace('"product": ', "product: ") in html


def test_대문_버튼이_제_상품으로_간다(client):
    html = appmod._with_pay(appmod._LANDING_HTML)
    cut = html.index("id=shortem")
    top = html[html.index("<section class=sc "):cut]
    assert set(re.findall(r'href="([^"]+)"', top)) == {"/pricing#shortcl", "#shortem"}
    assert "/pricing#shortcl" not in html[cut:]
    assert "product=" not in html[cut:]
    pricing = client.get("/pricing").text
    shortem_view = pricing[pricing.index("data-pv=shortem"):pricing.index("data-pv=shortcl id=shortcl")]
    assert "product=" not in shortem_view and "880,000" in shortem_view and "1,990,000" not in shortem_view


def _pay_done(client, monkeypatch, product):
    r = client.post("/api/pay/toss/order", json={"name": "a", "phone": "1", "email": "a@b.co", "product": product}).json()
    class Resp:
        status_code = 200
        def json(self):
            return {"status": "DONE", "method": "카드", "orderName": r["orderName"], "approvedAt": "2026-11-01"}
    monkeypatch.setattr(appmod.requests, "post", lambda *a, **k: Resp())
    return client.get("/pay/toss/success", params={"paymentKey": "k", "orderId": r["orderId"], "amount": r["amount"]}).text


def test_완료_화면은_숏클만_키_안내(client, monkeypatch):
    assert "라이선스 키와 설치 방법" in _pay_done(client, monkeypatch, "shortcl_basic")
    assert "라이선스 키와 설치 방법" not in _pay_done(client, monkeypatch, "shortem")


def test_실패하면_같은_상품으로_다시(client):
    r = client.post("/api/pay/toss/order", json={"name": "a", "phone": "1", "email": "a@b.co", "product": "shortcl_premium"}).json()
    assert 'href="/pay/toss?product=shortcl_premium"' in client.get("/pay/toss/fail", params={"orderId": r["orderId"]}).text
    r = client.post("/api/pay/toss/order", json={"name": "a", "phone": "1", "email": "a@b.co"}).json()
    assert 'href="/pay/toss"' in client.get("/pay/toss/fail", params={"orderId": r["orderId"]}).text


def test_마이페이지에_숏클_진입(client):
    html = (Path(appmod.__file__).parent / "static" / "settings.html").read_text(encoding="utf-8")
    assert 'href="/pricing#shortcl"' in html
    assert client.get("/api/pricing").json()["shortcl_upgrade_open"] is True


def test_결제_내역은_가입_없이도_숏템_숏클로_갈린다(client):
    client.post("/api/deposit_claim", json={"name": "입금자", "depositor": "입금", "contact": "010-1234-5678", "product": "shortcl_basic_upgrade"})
    client.post("/api/deposit_claim", json={"name": "옛신고", "depositor": "입금"})
    r = client.post("/api/pay/toss/order", json={"name": "카드", "phone": "010", "email": "buyer@b.co", "product": "shortcl_premium"}).json()
    with appmod._toss_db()._conn() as c:
        c.execute("UPDATE toss_payments SET status='DONE', approved_at='2026-11-02' WHERE order_id=?", (r["orderId"],))
    items = appmod._pay_ledger()
    by = {i["payer"]: i for i in items}
    assert by["카드"]["group"] == "숏클" and by["카드"]["plan"] == "프리미엄반" and by["카드"]["amount"] == 2990000
    assert by["카드"]["customer_id"] is None
    assert by["입금자"]["upgrade"] is True and by["입금자"]["amount"] == 110000 and by["입금자"]["phone"] == "010-1234-5678"
    assert by["옛신고"]["group"] == "숏템" and by["옛신고"]["amount"] == 880000
    badges = appmod._shortcl_badges(items, [{"id": 5, "email": "BUYER@b.co", "phone": ""}, {"id": 6, "email": "x@b.co", "phone": "01012345678"},
                                            {"id": 7, "email": "n@b.co", "phone": "0100000000"}])
    assert badges == {5: "프리미엄반", 6: "기본반"}


def test_결제_내역은_관리자만(client):
    assert client.get("/api/admin/pay_ledger", follow_redirects=False).status_code in (200, 401, 403, 307)
    html = (Path(appmod.__file__).parent / "static" / "admin.html").read_text(encoding="utf-8")
    assert "loadLedger()" in html and "id=plrows" in html


def test_옛_표에서도_결제_내역이_열린다(tmp_path, monkeypatch):
    import sqlite3
    path = str(tmp_path / "old.db")
    c = sqlite3.connect(path)
    c.execute("""CREATE TABLE toss_payments (order_id TEXT PRIMARY KEY, amount INTEGER, order_name TEXT, status TEXT,
                 payment_key TEXT, method TEXT, approved_at TEXT, raw TEXT, created_at TEXT, updated_at TEXT,
                 payer_name TEXT, payer_phone TEXT, payer_email TEXT)""")
    c.execute("INSERT INTO toss_payments(order_id,amount,order_name,status,approved_at,payer_name) VALUES('a',880000,'숏템메이커 2기 이용권','DONE','2026-10-01T10:00:00+09:00','옛카드')")
    c.execute("""CREATE TABLE deposit_claim (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, depositor TEXT NOT NULL,
                 contact TEXT, done INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)""")
    c.execute("INSERT INTO deposit_claim(name,depositor,created_at) VALUES('옛입금','입금','2026-10-02T01:00:00+00:00')")
    c.commit(); c.close()
    monkeypatch.setattr(appmod, "DB_PATH", path)
    Store(path)
    items = appmod._pay_ledger()
    assert [i["payer"] for i in items] == ["옛입금", "옛카드"]
    assert {i["group"] for i in items} == {"숏템"}


def test_시각_표기가_달라도_최신순(client):
    with appmod._toss_db()._conn() as c:
        c.execute("INSERT INTO toss_payments(order_id,amount,order_name,status,approved_at,payer_name) VALUES('x',1,'숏템메이커 2기 이용권','DONE','2026-11-02T08:00:00+09:00','이른결제')")
    st = Store(appmod.DB_PATH)
    st.add_deposit_claim("늦은신고", "입금")
    with st._conn() as c:
        c.execute("UPDATE deposit_claim SET created_at='2026-11-01T23:30:00+00:00'")
    assert [i["payer"] for i in appmod._pay_ledger()] == ["늦은신고", "이른결제"]


def test_무료회원도_숏클_정가는_살_수_있다(client, monkeypatch):
    monkeypatch.setattr(appmod, "_verify_session", lambda c: 7)
    monkeypatch.setattr(Store, "get_customer", lambda self, cid: {"plan": "free"})
    assert _order(client, "shortcl_basic").status_code == 200
    assert client.get("/pay/toss?product=shortcl_basic").status_code == 200


def test_비로그인_차액_화면이_다음_길을_알려준다(client):
    assert "숏클메이커 보기" in client.get("/pay/toss?product=shortcl_basic_upgrade").text


def test_결과물_영상은_칸에_맞춘다():
    assert ".sc-shot video{width:100%;height:100%" in appmod._LANDING_HTML
