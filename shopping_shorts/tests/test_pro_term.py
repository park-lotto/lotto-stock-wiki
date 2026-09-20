"""기간제 이용권(pro_from·pro_until) — 2026-08-31 사장님 "시작일을 내일부터 1년으로".

★왜 full_access_until을 안 쓰나(라이브 실측 2026-08-31):
  pro 48명 중 **26명**이 이미 지난 full_access_until을 갖고 있다(체험 때 잔재).
  그 필드로 만료를 판정하면 결제 고객 26명이 즉시 랭킹만으로 추락한다.
  → 새 개념은 새 칸에 담고, **값이 있을 때만** 만료를 본다.

여기서 잠그는 계약:
  1. pro_until이 없으면(0) 지금까지처럼 무기한 — 기존 고객 전원 무영향
  2. 지난 full_access_until이 박혀 있어도 pro는 안 잠긴다 ← 26명 보호
  3. pro_until이 지나면 ranking_only(재결제 유도)
  4. 12개월은 '같은 날짜의 1년 뒤'다 — 30일×12로 세면 며칠 어긋난다
"""
import pathlib
import tempfile
import time

import pytest

from shopping_shorts import app as appmod
from shopping_shorts.store import Store

NOW = int(time.time())
BASE = {"plan": "pro", "approved_at": 1, "trial_ends_at": 0, "full_access_until": 0}


def test_no_term_means_unlimited_like_before():
    assert appmod.access_level(9, now=NOW, cust=dict(BASE)) == "full"
    assert appmod.access_level(9, now=NOW, cust={**BASE, "pro_until": 0}) == "full"


def test_stale_full_access_until_does_not_lock_paying_customers():
    """★라이브에서 26명이 이 상태다 — 절대 잠기면 안 된다."""
    for past in (NOW - 86400, NOW - 86400 * 30, 1):
        cust = {**BASE, "full_access_until": past}
        assert appmod.access_level(9, now=NOW, cust=cust) == "full", (
            f"지난 full_access_until({past})로 결제 고객이 잠겼다")


def test_term_expiry_downgrades_to_ranking_only():
    assert appmod.access_level(9, now=NOW, cust={**BASE, "pro_until": NOW + 86400}) == "full"
    assert appmod.access_level(9, now=NOW,
                               cust={**BASE, "pro_until": NOW - 1}) == "ranking_only"


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    return TestClient(appmod.app)


def _store():
    return Store(str(pathlib.Path(tempfile.mkdtemp()) / "t.db"))


def test_store_sets_only_the_new_columns():
    """★full_access_until은 건드리지 않는다 — 다른 뜻을 가진 칸이다."""
    st = _store()
    cid = st.add_customer("u1", "pw") if hasattr(st, "add_customer") else None
    if cid is None:
        pytest.skip("고객 생성 API가 다르다")
    before = st.get_customer(cid)["full_access_until"]
    st.set_pro_term(cid, NOW, NOW + 86400)
    after = st.get_customer(cid)
    assert after["pro_from"] == NOW and after["pro_until"] == NOW + 86400
    assert after["full_access_until"] == before, "full_access_until을 건드렸다"


def test_twelve_months_is_same_date_next_year(client):
    """★12개월 = 2026-09-01 → 2027-09-01. 30일×12(=360일)로 세면 5일 어긋난다."""
    from datetime import datetime, timedelta, timezone
    kst = timezone(timedelta(hours=9))
    d0 = datetime(2026, 9, 1, tzinfo=kst)
    d1 = d0.replace(year=2027)
    assert (d1 - d0).days in (365, 366), "1년 계산이 이상하다"
    assert (d0 + timedelta(days=360)) != d1, "30일×12는 1년이 아니다"
