# -*- coding: utf-8 -*-
"""인포크용 상품 이미지(2026-09-27 김형관님 — 쿠팡 상품 페이지가 봇 차단이라 이미지를 못 구함)."""
from pathlib import Path
from shopping_shorts import coupang_partners as cp

ROOT = Path(__file__).resolve().parents[1]
IMG = "https://thumbnail6.coupangcdn.com/thumbnails/remote/492x492ex/image/a.jpg"


def test_이미지주소는_쿠팡이미지서버만():
    assert cp.is_product_image_url(IMG)
    assert not cp.is_product_image_url("https://evil.com/coupangcdn.com/a.jpg")
    assert not cp.is_product_image_url("http://thumbnail6.coupangcdn.com/a.jpg")
    assert not cp.is_product_image_url("")
    assert cp.is_product_image_url("https://ads-partners.coupang.com/image1/abc"), "파트너스 API가 주는 실제 호스트"
    assert not cp.is_product_image_url("https://www.coupang.com/vp/products/1"), "상품 페이지는 대상 아님"


def test_고른카드_이미지가_우선(monkeypatch):
    monkeypatch.setattr(cp, "search_products", lambda *a, **k: 1 / 0)
    assert cp.product_image("9644419727", "러닝화", IMG, "ak", "sk") == IMG


def test_없으면_같은_상품번호_카드만(monkeypatch):
    items = [{"product_id": "111", "image": "https://thumbnail1.coupangcdn.com/other.jpg"},
             {"product_id": "9644419727", "image": IMG}]
    monkeypatch.setattr(cp, "search_products", lambda *a, **k: {"items": items})
    assert cp.product_image("9644419727", "아식스 젤 카야노 31", "", "ak", "sk") == IMG
    monkeypatch.setattr(cp, "search_products", lambda *a, **k: {"items": items[:1]})
    assert cp.product_image("9644419727", "아식스", "", "ak", "sk") == "", "다른 상품 그림은 붙이지 않는다"
    assert cp.product_image("9644419727", "아식스", "", "", "") == "", "키 없으면 찾지 않는다"
    monkeypatch.setattr(cp, "search_products", lambda *a, **k: 1 / 0)
    assert cp.product_image("9644419727", "아식스", "", "ak", "sk") == "", "실패는 조용히 빈값"


def test_화면_배선():
    h = (ROOT / "static" / "produce.html").read_text(encoding="utf-8")
    assert "COUPANG.pickImage={image:it.image||'', pid:String(it.product_id||'')};" in h
    assert "body.image=COUPANG.pickImage.image; body.image_pid=COUPANG.pickImage.pid;" in h
    assert "/api/mix/product/${encodeURIComponent(MIX_JOB||'')}/image" in h and "⬇ 이미지 저장" in h
