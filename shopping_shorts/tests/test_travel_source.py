"""여행 소재 수집(관제 239) — 주소 판정·출처 문구·여기어때 상세 해석."""
import json

from shopping_shorts import travel_source as ts


def test_travel_site_yeogi_stay():
    t = ts.travel_site("https://www.yeogi.com/domestic-accommodations/7061?checkIn=2026-10-20")
    assert t == {"site": "yeogi", "site_name": "여기어때", "kind": "stay", "id": "7061"}


def test_travel_site_known_site_without_detail():
    t = ts.travel_site("https://trip.coupang.com/")
    assert t["site"] == "coupang" and t["kind"] is None


def test_travel_site_rejects_others():
    assert ts.travel_site("https://www.youtube.com/shorts/abc") is None
    assert ts.travel_site("ftp://yeogi.com/a") is None
    assert ts.travel_site("https://notyeogi.com/domestic-accommodations/1") is None
    assert ts.travel_site("") is None


def test_source_label():
    assert ts.source_label("yeogi") == "출처: 여기어때"
    assert ts.source_label("nope") == ""        # 모르면 지어내지 않는다


def _page(info):
    return '<html><script id="__NEXT_DATA__" type="application/json">%s</script></html>' % json.dumps(
        {"props": {"pageProps": {"accommodationInfo": info}}})


def test_yeogi_stay_parses_official_photos_only():
    info = {
        "meta": {"name": "테스트호텔", "grade": "5성급", "address": "인천", "review": {"rate": 9.6, "count": 10},
                 "newImages": [{"title": "야외 수영장 ", "image": "https://image.withstatic.com/a.jpg"},
                               {"title": None, "image": "https://image.withstatic.com/b.jpg"},
                               {"title": "객실", "image": "https://image.withstatic.com/a.jpg"}]},
        "rooms": [{"name": "스탠다드", "newImages": [{"image": "https://image.withstatic.com/r1.jpg"}],
                   "stay": {"price": {"discountPrice": 183000, "salePrice": 200000}}},
                  {"name": "디럭스", "stay": {"price": {"salePrice": 250000}}}],
        "theme": {"items": [{"name": "야외수영장"}, {"name": "사우나"}]},
    }
    d = ts._yeogi_stay("1", html=_page(info))
    assert d["name"] == "테스트호텔" and d["rating"] == 9.6 and d["review_count"] == 10
    assert d["price_from"] == 183000
    assert d["facilities"] == ["야외수영장", "사우나"]
    assert [p["url"].rsplit("/", 1)[1] for p in d["photos"]] == ["a.jpg", "b.jpg", "r1.jpg"]     # 중복 주소는 한 번
    assert d["photos"][0]["label"] == "야외 수영장" and d["photos"][1]["label"] is None and d["photos"][2]["label"] == "객실"
    assert d["source_label"] == "출처: 여기어때"


def test_fetch_unsupported_raises_with_reason():
    try:
        ts.fetch("https://trip.coupang.com/")
    except ValueError as e:
        assert "쿠팡트래블" in str(e)
    else:
        raise AssertionError("지원 안 하는 사이트는 이유와 함께 실패해야 한다")


# ── 여행 담기(/api/grab·/api/share → travel_basket) ────────────────────────────
from fastapi.testclient import TestClient      # noqa: E402
from shopping_shorts import app as appmod     # noqa: E402
from shopping_shorts.store import Store       # noqa: E402


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", False)
    # 보강은 진짜 사이트를 부른다 — 시험에서는 가짜 상세로 바꿔 끼운다
    monkeypatch.setattr(ts, "fetch", lambda url: {
        "name": "네스트호텔 인천", "price_from": 183000, "site_name": "여기어때", "source_label": "출처: 여기어때",
        "grade": "5성급", "address": "인천", "rating": 9.6, "review_count": 10, "facilities": ["야외수영장"],
        "photos": [{"url": "https://i/room.jpg", "label": "객실"}, {"url": "https://i/pool.jpg", "label": "야외 수영장"}]})
    return TestClient(appmod.app)


def test_grab_travel_goes_to_travel_basket_not_video(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/grab", params={"url": "https://www.yeogi.com/domestic-accommodations/7061", "title": "네스트"})
    assert r.status_code == 200 and "여행 담기에 담겼어요" in r.text and "출처: 여기어때" in r.text
    s = Store(str(tmp_path / "t.db"))
    assert s.mix_basket_list(customer_id=0) == []                  # 영상 즐겨찾기에는 안 들어간다
    items = s.travel_basket_list(customer_id=0)
    assert len(items) == 1 and items[0]["item_key"] == "yeogi:stay:7061"
    # 백그라운드 보강(TestClient 는 응답 뒤 백그라운드 작업까지 돈다)
    assert items[0]["name"] == "네스트호텔 인천" and items[0]["price"] == 183000
    assert items[0]["thumbnail"] == "https://i/pool.jpg"          # 대표 사진 = 물놀이 먼저
    assert items[0]["meta"]["source_label"] == "출처: 여기어때" and items[0]["meta"]["photo_count"] == 2
    r2 = c.get("/api/grab", params={"url": "https://www.yeogi.com/domestic-accommodations/7061"})
    assert "이미 담겨 있어요" in r2.text and len(s.travel_basket_list(customer_id=0)) == 1


def test_grab_travel_list_page_is_refused(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/grab", params={"url": "https://www.yeogi.com/"})
    assert "상세 페이지에서 눌러주세요" in r.text
    assert Store(str(tmp_path / "t.db")).travel_basket_list(customer_id=0) == []


def test_share_travel_link(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/share", json={"text": "여기 어때 https://www.yeogi.com/domestic-accommodations/7061?utm_source=x",
                                   "dest": "video"})
    j = r.json()
    assert j["ok"] and j["platform"] == "travel" and j["item_key"] == "yeogi:stay:7061"


def test_cover_photo_prefers_water():
    assert ts.cover_photo({"photos": [{"url": "a", "label": "객실"}, {"url": "b", "label": "야외 수영장"}]}) == "b"
    assert ts.cover_photo({"photos": [{"url": "a", "label": None}]}) == "a"
    assert ts.cover_photo({}) == ""


def test_travel_site_air_details():
    n = ts.travel_site("https://flight.naver.com/flights/international/ICN-NRT-20261121/NRT-ICN-20261127?adult=1")
    assert n["site"] == "naver" and n["kind"] == "air" and n["id"] == "international/ICN-NRT-20261121/NRT-ICN-20261127"
    o = ts.travel_site("https://tour.yanolja.com/air/search/c:SEL-c:SPK-20261030/c:SPK-c:SEL-20261102?cabin=ECONOMY")
    assert o["site"] == "nol" and o["kind"] == "air"
    assert ts.travel_site("https://flight.naver.com/")["kind"] is None


def test_best_items_one_site_failure_keeps_others(monkeypatch):
    ts._best_cache.clear()
    ok = [ts._air_item("nol", 1, "서울", "오사카", "", 239400, "왕복 총액", "2026-12-03", "2026-12-08", "RS", "u", "i")]
    monkeypatch.setitem(ts._BEST, ("air", "nol"), lambda: ok)
    def boom():
        raise RuntimeError("503")
    monkeypatch.setitem(ts._BEST, ("air", "naver"), boom)
    d = ts.best_items("air")
    assert d["items"] == ok and "503" in d["errors"]["네이버 항공권"]
    assert ok[0]["source_label"] == "출처: NOL 항공" and ok[0]["title"] == "서울 → 오사카"
    ts._best_cache.clear()
