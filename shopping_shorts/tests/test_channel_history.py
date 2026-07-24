"""수집 누적 히스토리(reel_history) — 채널 검색 시 '지난 한 달'(2026-07-22).

store: save_last_run이 shortcode별로 누적하고 first_seen 유지·30일 정리하는지.
api : /api/channel/history가 최신순·exclude 반영·무료등급 조회 허용인지.
"""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _iso(dt):
    return dt.isoformat()


def _item(sc, user="salim__mami", name="살림맘", views=100, comments=10, cat="홈템"):
    return {"shortcode": sc, "username": user, "name": name, "category": cat,
            "url": f"https://insta/{sc}", "thumbnail": f"t/{sc}.jpg",
            "caption": "cap", "views": views, "comments": comments}


# ── store ──────────────────────────────────────────────
def test_history_accumulates_across_collections(tmp_path):
    """수집을 두 번 하면(겹치는 shortcode + 새 것) 히스토리는 합집합으로 쌓인다."""
    s = Store(str(tmp_path / "t.db"))
    now = datetime.now(timezone.utc)
    s.save_last_run([_item("a"), _item("b")], _iso(now - timedelta(hours=48)))
    # 이틀 뒤 재수집: a는 48h 창에서 내려가고 b·c만 잡혔다 해도 a는 히스토리에 남아야 한다
    s.save_last_run([_item("b"), _item("c")], _iso(now))
    codes = {h["shortcode"] for h in s.channel_history("salim__mami")}
    assert codes == {"a", "b", "c"}


def test_history_keeps_first_seen_updates_last(tmp_path):
    """같은 영상 재수집 시 first_seen은 최초값 유지, last_seen·조회수는 갱신."""
    s = Store(str(tmp_path / "t.db"))
    now = datetime.now(timezone.utc)
    first = _iso(now - timedelta(hours=10))
    s.save_last_run([_item("a", views=100)], first)
    s.save_last_run([_item("a", views=250)], _iso(now))
    h = s.channel_history("salim__mami")[0]
    assert h["first_seen"] == first          # 최초 관측시각 보존
    assert h["last_seen"] == _iso(now)       # 마지막 관측시각 갱신
    assert h["views"] == 250                 # 최신 지표로 갱신


def test_history_prunes_after_30_days(tmp_path):
    """last_seen이 30일 넘은 행은 다음 수집 때 정리된다."""
    s = Store(str(tmp_path / "t.db"))
    now = datetime.now(timezone.utc)
    s.save_last_run([_item("old")], _iso(now))
    # old를 31일 전으로 늙힌다
    with s._conn() as c:
        c.execute("UPDATE reel_history SET last_seen=? WHERE shortcode=?",
                  (_iso(now - timedelta(days=31)), "old"))
    s.save_last_run([_item("fresh")], _iso(now))   # 이 수집이 정리 트리거
    codes = {h["shortcode"] for h in s.channel_history("salim__mami")}
    assert codes == {"fresh"}                       # old는 정리됨


def test_history_skips_items_without_keys(tmp_path):
    """shortcode/username 없는 항목은 저장하지 않는다(안전)."""
    s = Store(str(tmp_path / "t.db"))
    now = _iso(datetime.now(timezone.utc))
    s.save_last_run([{"username": "x", "views": 1},          # shortcode 없음
                     {"shortcode": "y", "views": 1},         # username 없음
                     _item("ok")], now)
    assert {h["shortcode"] for h in s.channel_history("salim__mami")} == {"ok"}


def test_channel_history_normalizes_and_excludes(tmp_path):
    """@대문자·공백 정규화 매칭 + exclude로 현재 랭킹 shortcode 제외."""
    s = Store(str(tmp_path / "t.db"))
    now = _iso(datetime.now(timezone.utc))
    s.save_last_run([_item("a"), _item("b")], now)
    hist = s.channel_history("  @Salim__Mami ", exclude=["a"])
    assert [h["shortcode"] for h in hist] == ["b"]   # a 제외, 정규화 매칭 성공


# ── api ────────────────────────────────────────────────
def _cookie(cid):
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(cid, exp)


def _api_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    return s


def test_api_channel_history_returns_latest_first(tmp_path, monkeypatch):
    s = _api_setup(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    s.save_last_run([_item("old")], _iso(now - timedelta(hours=20)))
    s.save_last_run([_item("new")], _iso(now))
    cid = s.create_customer("u1", "pw12")
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    r = c.get("/api/channel/history?username=salim__mami")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and [i["shortcode"] for i in body["items"]] == ["new", "old"]


def test_api_channel_history_free_user_allowed(tmp_path, monkeypatch):
    """무료(ranking_only) 등급도 랭킹 조회의 연장으로 히스토리 조회 가능(402 아님)."""
    s = _api_setup(tmp_path, monkeypatch)
    cid = s.create_customer("free1", "pw12")
    s.set_plan(cid, "free", full_access_until=0)   # 체험만료 → ranking_only
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    r = c.get("/api/channel/history?username=whoever")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_api_channel_history_requires_username(tmp_path, monkeypatch):
    s = _api_setup(tmp_path, monkeypatch)
    cid = s.create_customer("u1", "pw12")
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert c.get("/api/channel/history").status_code == 422
