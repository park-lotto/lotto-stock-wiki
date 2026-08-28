# -*- coding: utf-8 -*-
"""관리자 목록 일괄 조회가 **낱개 함수와 같은 값**을 주는지 (2026-08-24).

★왜 바꿨나: 고객 1명당 쿼리를 도는 구조(N+1)라 155명에서 900번 가까이 나갔고,
   목록이 뜨는 데 3.7초가 걸렸다. 그동안 화면은 비어 있어 "고객 0명"으로 보였다.

★이 테스트가 지키는 것: 빨라지는 것보다 **값이 같은 것**이 중요하다.
   일괄판이 낱개판과 다른 값을 주면, 관리자가 잘못된 잔액·사용량을 보고 판단한다.
"""
import pytest
from cryptography.fernet import Fernet

from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    st = Store(str(tmp_path / "t.db"))
    st.ensure_paywall_schema()
    return st


def test_usage_all_matches_usage_get(store):
    day = "2026-08-24"
    store.usage_incr(1, "lens", day)
    store.usage_incr(1, "lens", day)
    store.usage_incr(2, "render", day)
    bulk = store.usage_all(day)
    for cid in (1, 2, 3):
        for op in ("lens", "render", "script"):
            assert bulk.get(cid, {}).get(op, 0) == store.usage_get(cid, op, day), (
                f"cid={cid} op={op}에서 일괄판과 낱개판이 다르다")


def test_usage_all_is_scoped_to_the_day(store):
    """다른 날 사용량이 섞이면 안 된다."""
    store.usage_incr(1, "lens", "2026-08-23")
    store.usage_incr(1, "lens", "2026-08-24")
    assert store.usage_all("2026-08-24").get(1, {}).get("lens", 0) == 1


def test_points_balance_all_matches_points_balance(store):
    store.points_add(1, 500, "test")
    store.points_add(1, -200, "test")
    store.points_add(2, 300, "test")
    bulk = store.points_balance_all()
    for cid in (1, 2, 3):
        assert bulk.get(cid, 0) == store.points_balance(cid), f"cid={cid} 잔액 불일치"


def test_access_summary_all_matches_access_summary(store):
    since = "2026-08-17"
    store.record_access(1, "1.1.1.1", "UA-A", "2026-08-20")
    store.record_access(1, "2.2.2.2", "UA-A", "2026-08-21")
    store.record_access(2, "3.3.3.3", "UA-B", "2026-08-22")
    bulk = store.access_summary_all(since)
    for cid in (1, 2, 3):
        want = store.access_summary(cid, since)
        got = bulk.get(cid, {"ips": 0, "devices": 0})
        assert got == want, f"cid={cid} 접속요약 불일치: {got} != {want}"


def test_access_summary_all_respects_since(store):
    """기간 밖 접속은 세지 않는다."""
    store.record_access(1, "1.1.1.1", "UA", "2026-08-01")
    assert store.access_summary_all("2026-08-17").get(1, {"ips": 0})["ips"] == 0


def test_challenge_member_ids_matches_is_challenge_member(store):
    store.add_challenge_member(1, cohort="1기")
    ids = store.challenge_member_ids()
    for cid in (1, 2):
        assert (cid in ids) == store.is_challenge_member(cid), f"cid={cid} 챌린지 판정 불일치"


def test_admin_list_does_not_query_per_customer():
    """★루프 안에서 낱개 조회를 다시 부르면 N+1이 되살아난다."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    # 2026-08-29: 목록을 한 번만 읽어 재사용하도록 바뀌어(`_customers = st.list_customers()`)
    #   루프 머리가 `for cu in _customers:`가 됐다. 둘 다 받아준다 — 지켜야 할 것은
    #   "루프 안에서 낱개 조회를 하지 않는가"이지 루프를 어떻게 쓰느냐가 아니다.
    m = re.search(r"for cu in (?:st\.list_customers\(\)|_customers):", src)
    assert m, "관리자 목록 루프를 못 찾았다 — 이 테스트를 고쳐라"
    body = src[m.start(): src.index("\n    # ★설정", m.start())]
    for bad in ("st.usage_get(", "st.access_summary(", "points.balance(st",
                "st.is_challenge_member(",
                # 아래 셋은 2026-08-29 추가 — 고객마다 DB를 다시 치던 것들이다.
                # 이것들 때문에 목록이 라이브에서 18.2초 걸렸다(290명 실측).
                "_effective_limits(st", "_is_admin(_cid)", "_code_admin(_cid)"):
        assert bad not in body, f"관리자 목록 루프에 낱개 조회가 남아 있다: {bad}"
    assert re.search(r"usage_all|access_summary_all|points_balance_all", src), (
        "일괄 조회를 안 쓰고 있다")
    assert "_effective_limits_all(" in src, (
        "한도를 일괄로 안 구한다 — 고객마다 설정·키를 다시 읽으면 목록이 다시 느려진다")
