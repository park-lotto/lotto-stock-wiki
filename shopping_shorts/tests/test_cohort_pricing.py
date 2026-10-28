# -*- coding: utf-8 -*-
"""2기 모집 전환(2026-10-01 사장님 "2기모집 88만원으로, 10월"). 기수명·가격·다음 기수·마감은 **설정 한 곳**(_cohort_info)
— 화면(랜딩·요금·결제·설정·사이드바·안내)은 거기서 받아 그린다. '1기'·77만원 하드코딩 0곳."""
import re
from pathlib import Path
import pytest
from shopping_shorts import app as appmod
from shopping_shorts.store import Store

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("TOSS_CLIENT_KEY", "test_ck")
    monkeypatch.setenv("TOSS_SECRET_KEY", "test_sk")
    return Store(str(tmp_path / "t.db"))


def test_기본값은_2기_88만원_마감없음_다음은_3기_99만원(db):
    c = appmod._cohort_info()
    assert c["cohort"] == "2기" and c["next_cohort"] == "3기"
    assert c["amount"] == 880000 and c["next_price"] == 990000 and c["deadline"] == ""
    assert appmod._toss_order_name_amount() == ("숏템메이커 2기 이용권", 880000)


def test_설정으로_바꾸면_전부_따라온다(db):
    db.set_setting("cohort", "3기"); db.set_setting("toss_amount", "990000")
    db.set_setting("next_cohort", "4기"); db.set_setting("next_price", "1100000")
    c = appmod._cohort_info()
    assert (c["cohort"], c["amount"], c["next_cohort"], c["next_price"]) == ("3기", 990000, "4기", 1100000)
    assert appmod._toss_order_name_amount()[0] == "숏템메이커 3기 이용권"


def test_마감없으면_랜딩_카운트다운_블록이_빠지고_있으면_남는다(db):
    html = appmod._with_pay(appmod._LANDING_HTML)
    assert "id=cdD" not in html and "<!--DL-->" not in html and "<!--NODL-->" not in html
    assert "2기" in html and "880,000원" in html and "3기" in html and "990,000원" in html
    assert "1기" not in html and "770,000" not in html and "__COHORT__" not in html
    db.set_setting("recruit_deadline", "2026-10-31T23:59:59+09:00")
    html2 = appmod._with_pay(appmod._LANDING_HTML)
    assert "id=cdD" in html2 and "10월 31일" in html2 and "11월 1일" in html2


def test_api_pricing은_공개이고_같은_값을_준다(db):
    d = appmod.api_pricing()
    assert d["cohort"] == "2기" and d["amount"] == 880000 and d["next_price"] == 990000
    assert appmod._ranking_only_blocked("/api/pricing") is False   # 비로그인·무료 등급도 읽는다


def test_공개_화면에_1기_77만원_하드코딩이_없다():
    pub = ["landing.html", "static/notice_1gi.html", "static/settings.html", "static/sidebar.js",
           "static/setup.html", "static/challenge.html", "static/challenge_admin.html"]
    bad = {}
    for p in pub:
        t = (ROOT / p).read_text(encoding="utf-8")
        hits = [m.start() for m in re.finditer(r"1기|770,000|77만원|770000", t)]
        if hits:
            bad[p] = len(hits)
    assert not bad, bad
    a = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "숏템메이커 1기 이용권" not in a
    # _PRICING_TMPL(요금 FAQ)·_REFUND_BODY(환불규정)의 "1기 신청서의" 2곳은 기수 중립 "신청서의"로 바꿨다(2026-10-03 관제 087).
    assert a.count("1기 신청서") == 0
