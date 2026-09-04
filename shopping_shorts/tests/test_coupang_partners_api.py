"""쿠팡 파트너스 오픈API 연동(2026-09-04) — HMAC 호출·응답 파싱·정규화·BYOK 배선.
실제 네트워크는 안 탄다(_call을 가짜로 갈아끼움). 실호출 검증은 핸드오프의 사장님 키 실측."""
import json

import pytest

from shopping_shorts import coupang_partners as cp
from shopping_shorts import keyroute


def test_split_key_and_format():
    assert cp.split_key("abc:def") == ("abc", "def")
    assert cp.split_key("abc") == ("", "")
    assert cp.split_key(":def") == ("", "")


@pytest.mark.parametrize("url,want", [
    ("https://link.coupang.com/re/AFFSDP?lptag=AF9628186&pageKey=9572701928&traceid=V0-1",
     "https://www.coupang.com/vp/products/9572701928"),
    ("https://www.coupang.com/vp/products/123?itemId=9&vendorItemId=8&lptag=AF1",
     "https://www.coupang.com/vp/products/123"),
    ("https://link.coupang.com/a/gLcKSPsbwO", "https://link.coupang.com/a/gLcKSPsbwO"),   # 단축은 상품번호를 모른다
])
def test_canonical_product_url_strips_foreign_tracking(url, want):
    """★남의 추적링크(pageKey)를 그대로 쓰면 수수료가 남에게 간다 — 상품번호만 남긴다."""
    assert cp.canonical_product_url(url) == want


def test_auth_header_shape():
    h = cp._auth_header("GET", "/v2/x/products/search?keyword=a&limit=5", "AK", "SK")
    assert h.startswith("CEA algorithm=HmacSHA256, access-key=AK, signed-date=")
    assert ", signature=" in h and len(h.rsplit("signature=", 1)[1]) == 64


def test_search_products_parses_api_items(monkeypatch):
    seen = {}

    def fake_call(method, path, ak, sk, body=None, timeout=15):
        seen.update(method=method, path=path, ak=ak)
        return 200, {"rCode": "0", "data": {"productData": [
            {"productId": 9474858792, "productName": "태깅건 세트", "productPrice": 11900,
             "productImage": "https://img/x.jpg", "productUrl": "https://link.coupang.com/re/AFFSDP?lptag=AF1&pageKey=9474858792",
             "isRocket": True}]}}
    monkeypatch.setattr(cp, "_call", fake_call)
    monkeypatch.setattr(cp, "_record", lambda *a, **k: None)
    got = cp.search_products("의류 태깅건", limit=5, access_key="AK", secret_key="SK")
    assert got["ok"] and got["source"] == "api" and got["requires_approval"] is False
    assert seen["method"] == "GET" and "products/search?keyword=" in seen["path"] and seen["ak"] == "AK"
    it = got["items"][0]
    assert it["product_id"] == "9474858792" and it["url"] == "https://www.coupang.com/vp/products/9474858792"
    assert it["partner_url"].startswith("https://link.coupang.com/") and it["price"] == "11,900원"
    assert it["image"] and it["name"] == "태깅건 세트"


def test_search_products_without_keys_keeps_manual_flow(monkeypatch):
    monkeypatch.setattr(cp, "_call", lambda *a, **k: (_ for _ in ()).throw(AssertionError("호출하면 안 된다")))
    got = cp.search_products("x")
    assert got["ok"] and got["items"] == [] and got["requires_approval"] is True


def test_search_products_auth_dead_is_reported(monkeypatch):
    rec = []
    monkeypatch.setattr(cp, "_call", lambda *a, **k: (401, {"rCode": "401", "rMessage": "unauthorized"}))
    monkeypatch.setattr(cp, "_record", lambda outcome, **k: rec.append((outcome, k.get("customer_id"))))
    got = cp.search_products("x", access_key="AK", secret_key="SK", customer_id=340)
    assert not got["ok"] and got["items"] == [] and "키" in got["notice"]
    assert rec == [("auth_dead", 340)]        # 관측판 '회원 340의 키가 죽음'으로 이어진다


def test_to_deeplink_parses_and_passes_through_on_failure(monkeypatch):
    monkeypatch.setattr(cp, "_record", lambda *a, **k: None)
    monkeypatch.setattr(cp, "_call", lambda m, p, ak, sk, body=None, timeout=15: (200, {"rCode": "0", "data": [
        {"originalUrl": "https://www.coupang.com/vp/products/1", "shortenUrl": "https://link.coupang.com/a/AB",
         "landingUrl": "https://link.coupang.com/re/AFFSDP?pageKey=1"}]}))
    out = cp.to_deeplink(["https://www.coupang.com/vp/products/1"], "AK", "SK")
    assert out[0]["shorten_url"] == "https://link.coupang.com/a/AB" and out[0]["requires_approval"] is False
    monkeypatch.setattr(cp, "_call", lambda *a, **k: (0, {"error": "timeout"}))
    out = cp.to_deeplink(["https://www.coupang.com/vp/products/1"], "AK", "SK")
    assert out[0]["shorten_url"] == "" and "timeout" in out[0]["error"]
    assert cp.to_deeplink([], "AK", "SK") == []


def test_probe_key_true_only_on_rcode_zero(monkeypatch):
    monkeypatch.setattr(cp, "_call", lambda *a, **k: (200, {"rCode": "0", "data": []}))
    assert cp.probe_key("AK", "SK") is True
    monkeypatch.setattr(cp, "_call", lambda *a, **k: (401, {"rCode": "401"}))
    assert cp.probe_key("AK", "SK") is False
    assert cp.probe_key("", "") is False


def test_keyroute_coupang_is_personal_only():
    """회원 키만 쓴다 — 사장님 키로 폴백하면 수수료가 사장님에게 간다."""
    assert keyroute.SVC_COUPANG in keyroute.SERVICES and keyroute.SVC_COUPANG in keyroute.WIRED
    assert keyroute.SVC_COUPANG not in keyroute.POOLED
    assert keyroute._owner_keys(keyroute.SVC_COUPANG) == []

    class _St:
        def get_customer_keys_plain(self, cid, service):
            return ["AK:SK"] if cid == 7 else []
    keys, mine = keyroute.keys_for(_St(), 7, keyroute.SVC_COUPANG)
    assert keys == ["AK:SK"] and mine is True
    keys, mine = keyroute.keys_for(_St(), 8, keyroute.SVC_COUPANG)
    assert keys == [] and mine is False


def test_product_save_auto_deeplinks_with_member_key(monkeypatch, tmp_path):
    """★핵심 계약: 키 있는 회원이 상품을 저장하면 추적 링크가 자동으로 붙는다. 실패해도 저장은 된다."""
    from shopping_shorts import app as a
    from shopping_shorts.store import Store
    db = tmp_path / "t.db"
    monkeypatch.setattr(a, "DB_PATH", str(db))
    st = Store(str(db))
    st.create_mix_job("j1", ["u0"], 20, "free")          # test_app_product._ready와 같은 호출 형태
    monkeypatch.setattr(a, "_coupang_member_key", lambda customer_id=None: ("AK", "SK"))
    monkeypatch.setattr(cp, "_record", lambda *a_, **k: None)
    monkeypatch.setattr(cp, "_call", lambda m, p, ak, sk, body=None, timeout=15: (200, {"rCode": "0", "data": [
        {"originalUrl": body["coupangUrls"][0], "shortenUrl": "https://link.coupang.com/a/AUTO", "landingUrl": ""}]}))
    r = a.api_mix_product({"job_id": "j1", "url": "https://link.coupang.com/re/AFFSDP?lptag=AF_OTHER&pageKey=555",
                           "name": "테스트"})
    body = r if isinstance(r, dict) else json.loads(r.body)
    assert body["ok"], body
    assert body["product"]["url"] == "https://www.coupang.com/vp/products/555"      # 남의 추적 파라미터 제거
    assert body["product"]["partner_url"] == "https://link.coupang.com/a/AUTO" and body["product"]["partner_auto"]
    assert body["final_link"] == "https://link.coupang.com/a/AUTO"
    # 실패 경로 — 저장은 되고 사유가 남는다
    monkeypatch.setattr(cp, "_call", lambda *a_, **k: (0, {"error": "timeout"}))
    r = a.api_mix_product({"job_id": "j1", "url": "https://www.coupang.com/vp/products/556", "name": "t2"})
    body = r if isinstance(r, dict) else json.loads(r.body)
    assert body["ok"] and body["product"]["partner_url"] == "" and "timeout" in body["product"]["partner_error"]


def test_long_tracking_partner_url_is_shortened_on_save(monkeypatch, tmp_path):
    """검색 카드의 긴 추적 URL을 저장하면 짧은 링크로 바뀐다. 단축 실패면 긴 링크 유지(수수료는 같다)."""
    from shopping_shorts import app as a
    from shopping_shorts.store import Store
    db = tmp_path / "t.db"
    monkeypatch.setattr(a, "DB_PATH", str(db))
    Store(str(db)).create_mix_job("j1", ["u0"], 20, "free")
    monkeypatch.setattr(a, "_coupang_member_key", lambda customer_id=None: ("AK", "SK"))
    monkeypatch.setattr(cp, "_record", lambda *a_, **k: None)
    long_url = "https://link.coupang.com/re/AFFSDP?lptag=AF9628186&pageKey=9474858792&traceid=V0-1&token=abc"
    monkeypatch.setattr(cp, "_call", lambda m, p, ak, sk, body=None, timeout=15: (200, {"rCode": "0", "data": [
        {"originalUrl": body["coupangUrls"][0], "shortenUrl": "https://link.coupang.com/a/SHORT", "landingUrl": ""}]}))
    r = a.api_mix_product({"job_id": "j1", "url": "https://www.coupang.com/vp/products/9474858792",
                           "name": "x", "partner_url": long_url})
    body = r if isinstance(r, dict) else json.loads(r.body)
    assert body["product"]["partner_url"] == "https://link.coupang.com/a/SHORT"
    # 이미 짧은 링크면 API를 안 부른다
    monkeypatch.setattr(cp, "_call", lambda *a_, **k: (_ for _ in ()).throw(AssertionError("부르면 안 된다")))
    r = a.api_mix_product({"job_id": "j1", "url": "https://www.coupang.com/vp/products/9474858792",
                           "name": "x", "partner_url": "https://link.coupang.com/a/SHORT"})
    body = r if isinstance(r, dict) else json.loads(r.body)
    assert body["product"]["partner_url"] == "https://link.coupang.com/a/SHORT"
    # 단축 실패 → 긴 링크 유지, 에러 표시 없음
    monkeypatch.setattr(cp, "_call", lambda *a_, **k: (0, {"error": "timeout"}))
    r = a.api_mix_product({"job_id": "j1", "url": "https://www.coupang.com/vp/products/9474858792",
                           "name": "x", "partner_url": long_url})
    body = r if isinstance(r, dict) else json.loads(r.body)
    assert body["product"]["partner_url"] == long_url and not body["product"].get("partner_error")


def test_buffer_text_gets_coupang_block_automatically():
    """★2026-09-04 사장님 "예약발행까지 하면 자동으로 따라 들어가나?" — 이제 예약발행 글에
    쿠팡 링크·고지문구가 자동으로 붙는다. 유튜브·쓰레드=블록 전체 / 인스타·틱톡=고지문구+프로필 안내.
    이미 들어 있으면 두 번 안 붙는다. produce.html의 bufWithCoupang(순수 함수)을 node로 실행."""
    import pathlib, subprocess, tempfile
    html = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")
    i = html.index("function bufWithCoupang(")
    j = html.index("function bufLoadCoupang(")
    js = html[i:j] + r'''
const cp = {final_link: "https://link.coupang.com/a/AB", description_block: "🛒 상품\nhttps://link.coupang.com/a/AB\n\n이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."};
const yt = bufWithCoupang("제목\n\n설명", "youtube", cp);
const th = bufWithCoupang("제목", "threads", cp);
const ig = bufWithCoupang("캡션 #태그", "instagram", cp);
const twice = bufWithCoupang(yt, "youtube", cp);
const none = bufWithCoupang("제목", "youtube", null);
const ig2 = bufWithCoupang(ig, "instagram", cp);
console.log(JSON.stringify({yt, th, ig, twice_same: twice === yt, none, ig2_same: ig2 === ig}));
'''
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        path = f.name
    out = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert r["yt"].endswith(cp_block := "이에 따른 일정액의 수수료를 제공받습니다.") and "link.coupang.com/a/AB" in r["yt"]
    assert r["th"].count("link.coupang.com/a/AB") == 1
    assert "link.coupang.com" not in r["ig"] and "프로필 링크" in r["ig"] and r["ig"].endswith(cp_block)
    assert r["twice_same"] and r["ig2_same"]
    assert r["none"] == "제목"



def test_deeplink_endpoint_needs_key_and_canonicalizes(monkeypatch):
    """랭킹 카드 '🛒 쿠팡에 있나?' 모달의 딥링크 API — 키 없으면 안내(need_key), 있으면 짧은 링크."""
    from shopping_shorts import app as a
    monkeypatch.setattr(a, "_coupang_member_key", lambda customer_id=None: ("", ""))
    r = a.api_coupang_deeplink({"url": "https://link.coupang.com/re/AFFSDP?lptag=AF_X&pageKey=777"})
    assert r["ok"] is False and r["need_key"] and r["url"] == "https://www.coupang.com/vp/products/777"
    monkeypatch.setattr(a, "_coupang_member_key", lambda customer_id=None: ("AK", "SK"))
    monkeypatch.setattr(cp, "_record", lambda *a_, **k: None)
    monkeypatch.setattr(cp, "_call", lambda m, p, ak, sk, body=None, timeout=15: (200, {"rCode": "0", "data": [
        {"originalUrl": body["coupangUrls"][0], "shortenUrl": "https://link.coupang.com/a/ZZ", "landingUrl": ""}]}))
    r = a.api_coupang_deeplink({"url": "https://www.coupang.com/vp/products/777"})
    assert r["ok"] and r["shorten_url"] == "https://link.coupang.com/a/ZZ"
    bad = a.api_coupang_deeplink({"url": "https://naver.com/x"})
    assert bad.status_code == 422


def test_ranking_and_collection_have_coupang_find_button():
    """랭킹·담기 카드에 '🛒 쿠팡에 있나?' 버튼이 있고, 모달 본체는 sidebar.js 한 곳에만 있다(0순위-B)."""
    import pathlib
    st = pathlib.Path(__file__).resolve().parents[1] / "static"
    assert "쿠팡에 있나?" in (st / "index.html").read_text(encoding="utf-8")
    assert "쿠팡에 있나?" in (st / "collection.html").read_text(encoding="utf-8")
    sb = (st / "sidebar.js").read_text(encoding="utf-8")
    assert "window.ssCoupangFind = function" in sb and "/api/coupang/deeplink" in sb
    for name in ("index.html", "collection.html"):
        assert "/api/coupang/deeplink" not in (st / name).read_text(encoding="utf-8"), name
