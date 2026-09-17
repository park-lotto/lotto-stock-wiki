# -*- coding: utf-8 -*-
"""카드결제 버튼 주소의 단일 출처 _card_cta (2026-09-17).

토스 카드결제가 고객에게 '1회 한도 초과'로 막혀 스마트스토어 링크로 받는다.
관리자 설정 pay_url이 있으면 그것이 카드결제 주소다(토스 키가 있어도). 없으면 토스, 그것도 없으면 폴백.
"""
from shopping_shorts import app as appmod
from shopping_shorts.store import Store

SMART = "https://smartstore.naver.com/makerslab7/products/13765673887"


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    return Store(str(tmp_path / "t.db"))


def test_pay_url이_있으면_토스보다_우선(tmp_path, monkeypatch):
    s = _db(tmp_path, monkeypatch)
    s.set_setting("pay_url", SMART)
    monkeypatch.setenv("TOSS_CLIENT_KEY", "test_ck")
    monkeypatch.setenv("TOSS_SECRET_KEY", "test_sk")
    href, label = appmod._card_cta("/fallback", "폴백")
    assert href == SMART and "카드" in label
    assert 'href="' + SMART + '"' in appmod._deposit_card_html()


def test_pay_url이_없으면_토스(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setenv("TOSS_CLIENT_KEY", "test_ck")
    monkeypatch.setenv("TOSS_SECRET_KEY", "test_sk")
    assert appmod._card_cta("/fallback", "폴백")[0] == "/pay/toss"
    assert 'href="/pay/toss"' in appmod._deposit_card_html()


def test_둘_다_없으면_폴백(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.delenv("TOSS_CLIENT_KEY", raising=False)
    monkeypatch.delenv("TOSS_SECRET_KEY", raising=False)
    assert appmod._card_cta("/fallback", "폴백") == ("/fallback", "폴백")
    assert appmod._deposit_card_html() == ""


def test_랜딩_카드버튼이_pay_url로_간다(tmp_path, monkeypatch):
    s = _db(tmp_path, monkeypatch)
    s.set_setting("pay_url", SMART)
    monkeypatch.setenv("TOSS_CLIENT_KEY", "test_ck")
    monkeypatch.setenv("TOSS_SECRET_KEY", "test_sk")
    html = appmod._with_pay(appmod._LANDING_HTML)
    assert SMART in html and "/pay/toss" not in html
