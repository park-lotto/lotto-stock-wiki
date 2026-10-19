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
