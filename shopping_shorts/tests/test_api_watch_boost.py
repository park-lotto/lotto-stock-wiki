# -*- coding: utf-8 -*-
"""API 관측판 보강 (2026-09-02 사장님 지시 3건).

  ① 시간대별 그래프에 **실제 시각**을 표시 — 툴팁 말고 축에.
  ② 제미니 키 추가·삭제 기능
  ③ "사람들이 들어오면 몇 번 키가 어떻게 붙어 움직이는지" 생생하게

★③이 이 보강의 핵심이다. 지금은 '오늘 합계'만 있어 **지금 이 순간 누가 일하는지**를
  못 본다. 키별 타임라인(최근 호출이 시간축에 점으로)이 그 답이다.
"""
import pathlib

import pytest

from shopping_shorts import api_health as ah


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "t.db")
    ah.set_db_path(p)
    monkeypatch.setenv("API_HEALTH", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    yield p


# ── ③ 키별 실시간 타임라인 ────────────────────────────────────────────
def test_key_timeline_groups_by_key(db):
    """키 하나가 한 줄 — 그 키의 최근 호출이 시간순으로 담긴다."""
    ah.record("gemini", "ok", pool="shorts", key="AAAAAAAAAAkey111", op="대본생성")
    ah.record("gemini", "ok", pool="shorts", key="AAAAAAAAAAkey111", op="대본생성")
    ah.record("gemini", "rpm", pool="shorts", key="BBBBBBBBBBkey222", op="태깅")
    tl = ah.key_timeline(minutes=60)
    assert len(tl) == 2
    by = {r["key_tail"]: r for r in tl}
    a = by[ah.key_tail("AAAAAAAAAAkey111")]
    assert a["ok"] == 2 and a["fail"] == 0
    assert len(a["events"]) == 2          # 점으로 찍을 낱개 호출
    b = by[ah.key_tail("BBBBBBBBBBkey222")]
    assert b["fail"] == 1


def test_key_timeline_orders_busiest_first(db):
    """지금 제일 일하는 키가 맨 위 — 화면에서 바로 눈에 띄어야 한다."""
    for _ in range(3):
        ah.record("gemini", "ok", pool="shorts", key="XXXXXXXXXXbusy01", op="대본생성")
    ah.record("gemini", "ok", pool="shorts", key="YYYYYYYYYYidle01", op="대본생성")
    tl = ah.key_timeline(minutes=60)
    assert tl[0]["key_tail"] == ah.key_tail("XXXXXXXXXXbusy01")


def test_key_timeline_marks_owner_and_member(db):
    """★사장님 키와 회원 키를 갈라 보여준다 — 누가 부담하는지가 이 화면의 요점."""
    ah.record("gemini", "ok", pool="shorts", key="OOOOOOOOOOown001", owner="owner")
    ah.record("gemini", "ok", pool="shorts", key="MMMMMMMMMMmem001", owner="member")
    by = {r["key_tail"]: r for r in ah.key_timeline(minutes=60)}
    assert by[ah.key_tail("OOOOOOOOOOown001")]["owner"] == "owner"
    assert by[ah.key_tail("MMMMMMMMMMmem001")]["owner"] == "member"


def test_key_timeline_window_excludes_old(db):
    """창 밖(오래된) 호출은 안 들어온다 — '지금'을 보는 화면이다."""
    ah.record("gemini", "ok", pool="shorts", key="ZZZZZZZZZZold001", op="대본생성")
    import sqlite3
    c = sqlite3.connect(db)
    c.execute("UPDATE api_events SET ts='2020-01-01T00:00:00'")
    c.commit(); c.close()
    assert ah.key_timeline(minutes=60) == []


def test_key_timeline_empty_is_not_error(db):
    assert ah.key_timeline(minutes=60) == []


# ── ② 회원 제미니 키 관리 ─────────────────────────────────────────────
def test_admin_can_list_member_gemini_keys(db, tmp_path):
    """관리자가 회원 등록 키를 화면에서 본다(누가·언제·상태)."""
    from shopping_shorts.store import Store
    s = Store(str(tmp_path / "app.db"))
    s.ensure_paywall_schema()
    rows = ah.member_keys(s, service="gemini")
    assert isinstance(rows, list)


# ── ① 시간대 축 ───────────────────────────────────────────────────────
def test_hourly_carries_kst_label(db):
    """★그래프 축에 쓸 KST 시각을 **서버가** 준다.

    화면에서 UTC→KST를 다시 계산하면 판단이 두 곳에 생긴다(0순위-B).
    """
    ah.record("gemini", "ok", pool="shorts", key="AAAAAAAAAAkey111")
    import sqlite3
    c = sqlite3.connect(db)
    c.execute("UPDATE api_events SET ts='2026-09-01T03:30:00'")
    c.commit(); c.close()
    h = ah.aggregates(hours=24 * 365 * 10)["hourly"]
    assert h and "kst_hour" in h[0]
    assert h[0]["kst_hour"] == 12          # 03 UTC = 12 KST


def test_ui_hourly_axis_has_visible_labels():
    """축 라벨이 화면에 실제로 있어야 한다 — 툴팁만 있으면 '안 보인다'."""
    html = (pathlib.Path(__file__).resolve().parents[1]
            / "static" / "apiwatch.html").read_text(encoding="utf-8")
    assert "haxis" in html, "시간축 라벨 요소가 없다"


def test_ui_has_key_timeline_section():
    html = (pathlib.Path(__file__).resolve().parents[1]
            / "static" / "apiwatch.html").read_text(encoding="utf-8")
    assert "keyflow" in html, "키별 실시간 타임라인 구역이 없다"


# ── 엔드포인트 — 실제로 호출한다(import만으론 NameError를 못 잡는다) ──────
def test_api_apiwatch_carries_keyflow_and_member_keys(db, tmp_path, monkeypatch):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(appmod, "_require_admin", lambda r: None)
    from shopping_shorts.store import Store
    Store(str(tmp_path / "app.db")).ensure_paywall_schema()

    ah.record("gemini", "ok", pool="shorts", key="AAAAAAAAAAkey111", op="대본생성")
    out = appmod._api_apiwatch(request=None, hours=24)
    assert out["ok"] is True
    assert "keyflow" in out and "member_keys" in out
    assert out["keyflow"] and out["keyflow"][0]["ok"] == 1


def test_admin_key_delete_requires_ids(db, tmp_path, monkeypatch):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(appmod, "_require_admin", lambda r: None)
    from shopping_shorts.store import Store
    Store(str(tmp_path / "app.db")).ensure_paywall_schema()
    out = appmod._api_apiwatch_key_delete(request=None, body={})
    assert out["ok"] is False and "필요" in out["error"]


def test_admin_key_delete_removes_row(db, tmp_path, monkeypatch):
    """★관리자가 남의 이상한 키를 실제로 뺄 수 있어야 한다(09-01 사고의 처방)."""
    from shopping_shorts import app as appmod
    from shopping_shorts.store import Store
    p = str(tmp_path / "app.db")
    monkeypatch.setattr(appmod, "DB_PATH", p)
    monkeypatch.setattr(appmod, "_require_admin", lambda r: None)
    monkeypatch.setattr(appmod, "_resync_pools", lambda s: None)
    # ★keycrypt는 마스터키를 **임포트 시점에** 읽는다 → reload 필요(기존 BYOK 테스트 관습).
    import importlib
    from shopping_shorts import keycrypt
    monkeypatch.setenv("BYOK_MASTER_KEY",
                       "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To=")
    importlib.reload(keycrypt)
    s = Store(p)
    s.ensure_paywall_schema()
    s.add_customer_key(261, "gemini", "AIzaSyTESTKEY000000000000000000000000000")
    rows = s.list_all_customer_keys("gemini")
    assert len(rows) == 1
    out = appmod._api_apiwatch_key_delete(
        request=None, body={"customer_id": 261, "id": rows[0]["id"]})
    assert out["ok"] is True
    assert s.list_all_customer_keys("gemini") == []
