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



@pytest.mark.parametrize("raw,want", [
    ("태그건 의류 라벨건 초간편 의류태그건 세트 라벨총 택건 바늘 1000개 포함, 핑크, 1개", "태그건 의류 라벨건"),
    ("스마트 미니세탁기 건조기 분리형 속옷세탁기 손빨래 소형", "미니세탁기 건조기 분리형"),
    ("힘좋은 실용적인 원목 우드 트레이 타원형 B타입, 브라운, 1개", "원목 우드 트레이 타원형"),
    ("국내생산 우드 원형트레이, 1개, 기본", "우드 원형트레이"),
    ("짧은이름", "짧은이름"),
    ("", ""),
])
def test_short_name_uses_only_original_words(raw, want):
    """★긴 쿠팡 상품명을 인포크 버튼·DM용으로 줄인다(2026-09-04). 지어내지 않고 원본 단어만 쓴다."""
    from shopping_shorts.coupang_partners import short_name
    got = short_name(raw)
    assert got == want, got
    for w in got.split():
        assert w in raw, (w, raw)          # 없는 말이 섞이면 다른 상품이 된다


def test_dm_set_uses_short_name_but_keeps_full_listing():
    """등록 이름은 원본 유지(인포크 검색이 훑는다), 버튼·DM 타이틀만 짧게."""
    from shopping_shorts.coupang_partners import dm_set
    long_nm = "태그건 의류 라벨건 초간편 의류태그건 세트 라벨총 택건 바늘 1000개 포함, 핑크, 1개"
    d = dm_set("29", long_nm)
    assert d["listing_name"] == "29. " + long_nm
    assert d["short_name"] == "태그건 의류 라벨건"
    assert d["dm_title"] == "(29번) 태그건 의류 라벨건"
    d0 = dm_set("", long_nm)
    assert d0["dm_title"] == "태그건 의류 라벨건" and d0["listing_name"] == long_nm
