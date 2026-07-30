"""쿠팡 파트너스 연결 순수 로직(2026-07-28, 승인 전 수동 흐름)."""
import pytest

from shopping_shorts import coupang_partners as cp


def test_search_url_encodes_keyword():
    url = cp.search_url("실리콘 다용도 집게")
    assert url.startswith("https://www.coupang.com/np/search?q=")
    assert " " not in url


def test_parse_product_url_strips_tracking_params():
    raw = ("https://www.coupang.com/vp/products/1234567890"
           "?itemId=99&vendorItemId=88&searchId=abc&rank=3&isAddedCart=")
    out = cp.parse_product_url(raw)
    assert out["product_id"] == "1234567890"
    assert "searchId" not in out["url"] and "rank" not in out["url"]
    assert "itemId=99" in out["url"] and "vendorItemId=88" in out["url"]


def test_parse_product_url_keeps_partners_shorten_link_as_is():
    raw = "https://link.coupang.com/a/bXyZ12"
    assert cp.parse_product_url(raw) == {"product_id": "", "url": raw}


@pytest.mark.parametrize("bad", [
    "", "   ", "https://smartstore.naver.com/x/products/1",
    "https://www.coupang.com/np/search?q=집게",   # 검색결과 페이지는 상품이 아니다
])
def test_parse_product_url_rejects_non_product(bad):
    assert cp.parse_product_url(bad) is None


def test_build_product_rejects_non_product_url():
    with pytest.raises(ValueError):
        cp.build_product(keyword="집게", url="https://example.com/thing")


def test_build_product_record_shape():
    p = cp.build_product(keyword="집게", url="https://www.coupang.com/vp/products/55",
                         name="실리콘 집게", partner_url="https://link.coupang.com/a/q")
    assert p["product_id"] == "55"
    assert p["name"] == "실리콘 집게"
    assert p["inpock_registered"] is False


def test_final_link_prefers_partner_url():
    p = cp.build_product(url="https://www.coupang.com/vp/products/55",
                         partner_url="https://link.coupang.com/a/q")
    assert cp.final_link(p) == "https://link.coupang.com/a/q"
    p2 = cp.build_product(url="https://www.coupang.com/vp/products/55")
    assert cp.final_link(p2) == "https://www.coupang.com/vp/products/55"
    assert cp.final_link(None) == ""


def test_description_block_has_link_and_disclosure():
    p = cp.build_product(url="https://www.coupang.com/vp/products/55", name="실리콘 집게")
    block = cp.description_block(p)
    assert "실리콘 집게" in block
    assert "/vp/products/55" in block
    assert cp.DISCLOSURE in block          # 공정위 대가성 고지 — 빠지면 안 된다
    assert cp.description_block(None) == ""


def test_search_products_without_keys_returns_search_url_only():
    out = cp.search_products("실리콘 집게")
    assert out["ok"] and out["items"] == [] and out["requires_approval"] is True
    assert out["search_url"].startswith("https://www.coupang.com/np/search")


def test_search_products_empty_keyword_is_error():
    assert cp.search_products("  ")["ok"] is False


def test_to_deeplink_without_keys_passes_through():
    out = cp.to_deeplink(["https://www.coupang.com/vp/products/55", ""])
    assert len(out) == 1
    assert out[0]["original_url"].endswith("/55")
    assert out[0]["shorten_url"] == "" and out[0]["requires_approval"] is True
