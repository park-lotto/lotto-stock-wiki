"""쿠팡 상품검색 크롤 — 순수 파싱/설정 테스트(브라우저 없이 돈다).

실제 크롤은 주거용 IP + 헤드풀 크롬이 있어야 하므로 CI에서 못 돌린다. 그래서
브라우저에서 뽑아온 raw dict(실제 DOM에서 관측한 모양 그대로)를 고정해두고
파싱 계약만 못 박는다."""
import pytest

from shopping_shorts import config, coupang_search

# 2026-07-29 실제 검색결과("주방 가림막")에서 관측한 raw 모양.
RAW_REAL = [{
    "product_id": "8190563274",
    "href": "/vp/products/8190563274?itemId=23438083801&vendorItemId=90464962503"
            "&q=주방가림막&searchId=43bcbf4a4164959&sourceType=search&searchRank=2&rank=2",
    "name": "코멧 키친 접이식 레인지 가림막 아이보리 + 파우치 세트, 1세트",
    "image": "https://thumbnail.coupangcdn.com/thumbnails/remote/657x657q90trim/a.jpg",
    "price_text": "19,900원\n20%\n15,890원",
    "rating_text": "(2,226)",
    "info_text": "코멧 키친 접이식 레인지 가림막\n15,890원\n로켓배송\n(2,226)",
}]


def test_parse_items_normalizes_url_and_price():
    [item] = coupang_search.parse_items(RAW_REAL)
    # 검색 유입 추적값(searchId·rank·q)은 떨어지고 상품 식별자만 남는다.
    assert item["url"] == ("https://www.coupang.com/vp/products/8190563274"
                           "?itemId=23438083801&vendorItemId=90464962503")
    assert "searchId" not in item["url"] and "rank" not in item["url"]
    # 정가·할인율·판매가가 쌓여 있으면 마지막(=실제 판매가)을 쓴다.
    assert item["price"] == "15,890원"
    assert item["rating"] == "(2,226)"
    assert item["rocket"] is True
    assert item["is_ad"] is False
    assert item["product_id"] == "8190563274"


def test_parse_items_marks_ads_but_keeps_them():
    raw = [dict(RAW_REAL[0], product_id="1", href="/vp/products/1",
                info_text="어쩌구\n광고")]
    [item] = coupang_search.parse_items(raw)
    assert item["is_ad"] is True   # 버리지 않는다 — 광고가 잘 팔리는 상품인 경우가 많다


def test_parse_items_dedupes_and_drops_broken():
    raw = [
        dict(RAW_REAL[0]),
        dict(RAW_REAL[0]),                                   # 같은 상품 중복
        {"product_id": "9", "href": "/np/search?q=x"},        # 상품 URL 아님
        {"product_id": "", "href": "/vp/products/7"},          # id 없음
    ]
    items = coupang_search.parse_items(raw)
    assert [i["product_id"] for i in items] == ["8190563274"]


def test_parse_items_respects_limit():
    raw = [dict(RAW_REAL[0], product_id=str(i), href=f"/vp/products/{i}")
           for i in range(1, 10)]
    assert len(coupang_search.parse_items(raw, limit=3)) == 3


@pytest.mark.parametrize("text,expected", [
    ("210,000원\n9%\n190,000원", "190,000원"),
    ("15,890원", "15,890원"),
    ("", ""),
    ("품절", ""),
])
def test_pick_price(text, expected):
    assert coupang_search._pick_price(text) == expected


def test_proxy_arg_splits_credentials():
    p = coupang_search._proxy_arg("http://user1:pa%40ss@proxy.example.com:8080")
    assert p == {"server": "http://proxy.example.com:8080",
                 "username": "user1", "password": "pa@ss"}


def test_proxy_arg_empty_is_none():
    assert coupang_search._proxy_arg("") is None
    assert coupang_search._proxy_arg(None) is None


def test_search_disabled_returns_manual_fallback(monkeypatch):
    """★기능이 꺼져 있어도 예외 없이 검색 링크는 준다 — 수동 흐름이 살아 있어야 한다."""
    monkeypatch.setattr(config, "COUPANG_SEARCH_ENABLED", False)
    r = coupang_search.search("주방 가림막")
    assert r["ok"] is False and r["items"] == []
    assert r["search_url"].startswith("https://www.coupang.com/np/search?q=")
    assert r["notice"]


def test_search_empty_keyword():
    r = coupang_search.search("  ")
    assert r["ok"] is False and r["items"] == [] and r["search_url"] == ""
